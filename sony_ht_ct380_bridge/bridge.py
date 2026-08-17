#!/usr/bin/env python3
import asyncio,json,logging,os,select,socket,urllib.error,urllib.request
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt
from dbus_next import BusType,Variant
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface,method
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
L=logging.getLogger("sony-ht-ct380")
UUID="91819D50-5D72-4478-A001-29EB2C763568";BASE="sony_ht_ct380";AVAIL=BASE+"/availability"
MODES={"ClearAudio+":0x0FFF,"Standard":0x1FFF,"Movie":0x2FFF,"Sports":0x3FFF,"Game":0x4FFF,"Music":0x5FFF,"Portable Audio":0x6FFF,"Effect Off":0x7FFF}
MODE_IDS={v:k for k,v in MODES.items()}
INPUTS={"TV":(0,0x17,"TV"),"HDMI 1":(1,0x18,"HDMI 1"),"HDMI 2":(2,0x18,"HDMI 2"),"HDMI 3":(3,0x18,"HDMI 3"),"Analog":(4,0x19,"Analog"),"BT Audio":(5,0x00,"Bluetooth Audio")}
def escape(data):
 out=bytearray()
 for b in data:
  if b in (60,61,62):out.extend((61,b-16))
  else:out.append(b)
 return bytes(out)
def frame(kind,seq,payload=b""):
 body=bytes((kind,seq))+len(payload).to_bytes(4,"big")+payload
 body+=bytes((sum(body)&255,))
 return b"\x3e"+escape(body)+b"\x3c"
class Parser:
 def __init__(self):self.on=False;self.esc=False;self.buf=bytearray()
 def feed(self,data):
  result=[]
  for b in data:
   if not self.on:
    if b==62:self.on=True;self.buf.clear()
    continue
   if self.esc:self.buf.append((b+16)&255);self.esc=False;continue
   if b==61:self.esc=True;continue
   if b==62:self.buf.clear();continue
   if b!=60:self.buf.append(b);continue
   raw=bytes(self.buf);self.on=False;self.esc=False;self.buf.clear()
   if len(raw)>=7:
    n=int.from_bytes(raw[2:6],"big")
    if len(raw)==n+7 and (sum(raw[:-1])&255)==raw[-1]:result.append((raw[0],raw[1],raw[6:-1]))
    else:L.warning("Discarded invalid frame %s",raw.hex(" ").upper())
  return result
def readfd(fd):
 ready,_,_=select.select([fd],[],[],1)
 return os.read(fd,4096) if ready else None
def startup():
 now=datetime.now();bcd=lambda n:((n//10)<<4)|(n%10)
 return [("launcher",bytes((0x10,2,1))),("clock",bytes((1,bcd(now.hour),bcd(now.minute),bcd(now.second)))),("settings",bytes((5,0,0,1)))]
class Profile(ServiceInterface):
 def __init__(self,q):super().__init__("org.bluez.Profile1");self.q=q
 @method()
 def Release(self)->None:L.info("BlueZ released profile")
 @method()
 def NewConnection(self,device:"o",fd:"h",props:"a{sv}")->None:
  L.info("RFCOMM channel 11 opened by %s",device);self.q.put_nowait(os.dup(fd))
 @method()
 def RequestDisconnection(self,device:"o")->None:L.info("Disconnect requested: %s",device)
class Bridge:
 def __init__(self,loop,mac):
  self.loop=loop;self.mac=mac;self.session=None;self.handshake_started=None;self.states={};self.reconnect_control=None;self.device_connected=None
  self.recovery_attempts=0;self.recovery_next=0;self.recovery_warned=False;self.missing_since=None
  self.mq=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="sony_ht_ct380_bridge")
  if os.getenv("MQTT_USER"):self.mq.username_pw_set(os.getenv("MQTT_USER"),os.getenv("MQTT_PASSWORD",""))
  self.mq.will_set(AVAIL,"offline",1,True);self.mq.on_connect=self.connected;self.mq.on_connect_fail=self.connect_failed;self.mq.on_disconnect=self.disconnected;self.mq.on_message=self.message
  self.mq.enable_logger(L);self.mq.reconnect_delay_set(min_delay=2,max_delay=30)
 def start(self):
  host=os.environ["MQTT_HOST"];port=int(os.getenv("MQTT_PORT","1883"))
  target=host
  try:
   addresses=sorted({item[4][0] for item in socket.getaddrinfo(host,port,socket.AF_INET,socket.SOCK_STREAM)})
   if addresses:target=addresses[0]
   L.info("MQTT broker %s resolved to %s",host,target)
  except OSError as exc:L.warning("MQTT DNS lookup failed for %s: %s",host,exc)
  L.info("Connecting to MQTT at %s:%d (credentials=%s)",target,port,"yes" if os.getenv("MQTT_USER") else "no")
  self.mq.connect_async(target,port,60);self.mq.loop_start()
 def connect_failed(self,client,user):L.error("MQTT TCP connection failed; retrying")
 def disconnected(self,client,user,flags,reason,properties):
  if reason!=0:L.warning("MQTT disconnected: %s",reason)
 def discover(self):
  dev={"identifiers":["sony_ht_ct380_tandem"],"name":"Sony HT-CT380","manufacturer":"Sony","model":"HT-CT380","sw_version":"2.033","connections":[["mac",self.mac]]}
  common={"availability_topic":AVAIL,"payload_available":"online","payload_not_available":"offline","device":dev,"origin":{"name":"Sony HT-CT380 bridge","sw_version":"0.5.16"}}
  entities=[
   ("number","volume",{"name":"Volume","unique_id":"sony_ht_ct380_volume","command_topic":BASE+"/volume/set","state_topic":BASE+"/volume/state","min":0,"max":50,"step":1,"mode":"slider","icon":"mdi:volume-high"}),
   ("sensor","normalized_volume",{"name":"Normalized Volume","unique_id":"sony_ht_ct380_normalized_volume","state_topic":BASE+"/volume/state","value_template":"{{ value | float / 50 }}","entity_category":"diagnostic","icon":"mdi:volume-medium"}),
   ("number","subwoofer",{"name":"Subwoofer","unique_id":"sony_ht_ct380_subwoofer","command_topic":BASE+"/subwoofer/set","state_topic":BASE+"/subwoofer/state","min":0,"max":12,"step":1,"mode":"slider","icon":"mdi:speaker"}),
   ("switch","night_mode",{"name":"Night Mode","unique_id":"sony_ht_ct380_night_mode","command_topic":BASE+"/night_mode/set","state_topic":BASE+"/night_mode/state","payload_on":"ON","payload_off":"OFF","icon":"mdi:weather-night"}),
   ("select","sound_mode",{"name":"Sound Mode","unique_id":"sony_ht_ct380_sound_mode","command_topic":BASE+"/sound_mode/set","state_topic":BASE+"/sound_mode/state","options":list(MODES),"icon":"mdi:surround-sound"}),
   ("select","input",{"name":"Input","unique_id":"sony_ht_ct380_input","command_topic":BASE+"/input/set","state_topic":BASE+"/input/state","options":list(INPUTS),"icon":"mdi:video-input-hdmi"}),
   ("binary_sensor","connection",{"name":"Control Connection","unique_id":"sony_ht_ct380_connection","state_topic":BASE+"/connection/state","payload_on":"ON","payload_off":"OFF","device_class":"connectivity"}),
   ("binary_sensor","recovery_problem",{"name":"Control Recovery Problem","unique_id":"sony_ht_ct380_recovery_problem","state_topic":BASE+"/recovery_problem/state","payload_on":"ON","payload_off":"OFF","device_class":"problem","entity_category":"diagnostic"}),
   ("button","reconnect_control",{"name":"Reconnect Control","unique_id":"sony_ht_ct380_reconnect_control","command_topic":BASE+"/reconnect_control/set","payload_press":"PRESS","icon":"mdi:bluetooth-connect"})]
  for domain,obj,cfg in entities:
   payload=dict(common);payload.update(cfg)
   if domain=="button" or obj=="recovery_problem":
    for key in ("availability_topic","payload_available","payload_not_available"):payload.pop(key,None)
   self.mq.publish("homeassistant/"+domain+"/"+BASE+"/"+obj+"/config",json.dumps(payload),1,True)
 def connected(self,client,user,flags,reason,properties):
  if reason!=0:L.error("MQTT failed: %s",reason);return
  L.info("MQTT connected; publishing discovery");self.discover();client.subscribe(BASE+"/+/set")
  client.publish(AVAIL,"online" if self.session else "offline",1,True)
  for k,v in self.states.items():self.state(k,v)
 def message(self,client,user,msg):
  key=msg.topic.split("/")[-2];value=msg.payload.decode(errors="replace").strip()
  asyncio.run_coroutine_threadsafe(self.command(key,value),self.loop)
 def state(self,key,value):
  self.states[key]=str(value);self.mq.publish(BASE+"/"+key+"/state",str(value),1,True)
 def set_session(self,session):
  self.session=session;online=bool(session and session.linked)
  self.mq.publish(AVAIL,"online" if online else "offline",1,True);self.state("connection","ON" if online else "OFF")
  if online:
   self.missing_since=None;self.recovery_attempts=0;self.recovery_next=0
   if self.recovery_warned:
    self.recovery_warned=False;self.state("recovery_problem","OFF");self.notify(False)
 def notify(self,failed):
  token=os.getenv("SUPERVISOR_TOKEN")
  if not token:return
  service="create" if failed else "dismiss"
  if failed:
   data={"title":"Sony HT-CT380 control disconnected","message":"The soundbar is connected by Bluetooth, but its Sony control channel did not recover after two attempts. Press Reconnect Control or check the bridge logs.","notification_id":"sony_ht_ct380_control_recovery"}
  else:data={"notification_id":"sony_ht_ct380_control_recovery"}
  def post():
   url=os.getenv("SUPERVISOR_API","http://supervisor")+"/core/api/services/persistent_notification/"+service
   req=urllib.request.Request(url,data=json.dumps(data).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},method="POST")
   try:
    with urllib.request.urlopen(req,timeout=10) as response:response.read()
   except (OSError,urllib.error.URLError) as exc:L.warning("Could not %s Home Assistant recovery notification: %s",service,exc)
  self.loop.run_in_executor(None,post)
 async def recovery_watchdog(self):
  L.info("Automatic control recovery watchdog started");self.state("recovery_problem","OFF")
  while True:
   await asyncio.sleep(2)
   if self.session and self.session.linked:
    self.missing_since=None;self.recovery_attempts=0;self.recovery_next=0;continue
   now=self.loop.time()
   if self.handshake_started is not None:
    elapsed=now-self.handshake_started
    if elapsed<60:continue
    L.warning("Sony handshake has taken %.0f seconds; recovery is allowed again",elapsed)
    self.handshake_started=None
   try:connected=bool(self.device_connected and await self.device_connected())
   except Exception as exc:
    L.warning("Automatic recovery could not read BlueZ state: %s",exc);continue
   if not connected:
    self.missing_since=None;self.recovery_attempts=0;self.recovery_next=0;continue
   if self.missing_since is None:
    self.missing_since=now;L.info("Bluetooth is connected without Sony control; allowing 2-second startup grace period");continue
   if now-self.missing_since<2 or now<self.recovery_next:continue
   if self.recovery_attempts>=2:
    if not self.recovery_warned:
     self.recovery_warned=True;self.state("recovery_problem","ON");self.notify(True)
     L.error("Sony control recovery stopped after two attempts; manual Reconnect Control is available")
    continue
   self.recovery_attempts+=1;L.warning("Automatic Sony control recovery attempt %d/2",self.recovery_attempts)
   await self.reconnect_control("automatic recovery");self.recovery_next=self.loop.time()+90
 async def command(self,key,value):
  if key=="reconnect_control":
   if self.reconnect_control:
    self.recovery_warned=False;self.state("recovery_problem","OFF");self.notify(False)
    self.recovery_attempts=0;self.missing_since=self.loop.time();await self.reconnect_control("manual button")
   else:L.error("Bluetooth reconnect handler is not ready")
   return
  if not self.session or not self.session.linked:L.warning("Ignored %s while control link offline",key);return
  confirm=None;publish_after_ack=None
  try:
   if key=="volume":
    n=max(0,min(50,round(float(value))));payload=bytes((0x93,1,2,n));value=str(n)
   elif key=="subwoofer":
    n=max(0,min(12,round(float(value))));payload=bytes((0x93,0x20,3,0x0F,0xFF,1,1,n));value=str(n)
    self.session.subwoofer_direction=1
    publish_after_ack=("subwoofer",value)
   elif key=="night_mode":
    on=value.upper() in ("ON","1","TRUE");payload=bytes((0x93,0x20,1,0x0F,0xFF,1,1,int(on)));value="ON" if on else "OFF"
    confirm=bytes((0x91,0x20,1,0x0F,0xFF,0))
   elif key=="sound_mode":
    cat=MODES[value];payload=bytes((0x93,0x12,cat>>8,cat&255,0,0))
   elif key=="input":
    idx,source,title=INPUTS[value];name=title.encode();payload=bytes((0x30,idx,1,source,len(name)))+name
    self.session.pending_input=value
   else:return
  except (KeyError,ValueError):L.warning("Invalid %s=%r",key,value);return
  L.info("HA command %s=%s payload=%s",key,value,payload.hex(" ").upper())
  await self.session.send(payload,"set "+key,wait_ack=bool(publish_after_ack))
  if publish_after_ack:self.state(*publish_after_ack)
  if confirm:
   await asyncio.sleep(.75)
   await self.session.send(confirm,"confirm "+key)
class Session:
 def __init__(self,fd,bridge):
  self.fd=fd;self.bridge=bridge;self.parser=Parser();self.q=asyncio.Queue();self.ready=asyncio.Event()
  self.ready.set();self.volume_reply=asyncio.Event();self.subwoofer_reply=asyncio.Event();self.seq=0;self.started=False;self.linked=False;self.closed=False
  self.subwoofer_direction=1;self.pending_input=None
 async def send(self,payload,label,wait_ack=False):
  result=self.bridge.loop.create_future() if wait_ack else None
  await self.q.put((payload,label,result))
  if result:return await result
 def fail(self,reason):
  if self.closed:return
  self.closed=True;L.error("Sony control session is stale: %s",reason)
  self.linked=False
  if self.bridge.session is self:self.bridge.set_session(None)
  self.bridge.missing_since=self.bridge.loop.time()-20
  try:os.close(self.fd)
  except OSError:pass
 async def writer(self):
  while True:
   payload,label,result=await self.q.get();await self.ready.wait();self.ready.clear()
   for attempt in range(1,4):
    await asyncio.to_thread(os.write,self.fd,frame(0,self.seq,payload))
    L.info("TX %s seq=%d %s%s",label,self.seq,payload.hex(" ").upper(),"" if attempt==1 else " retry="+str(attempt))
    try:
     ack_timeout=5.0 if not self.linked else 2.0
     await asyncio.wait_for(self.ready.wait(),ack_timeout)
     if result and not result.done():result.set_result(True)
     break
    except asyncio.TimeoutError:
     L.warning("No Sony ACK for %s (attempt %d/3)",label,attempt)
     if attempt<3:
      self.seq^=1
      L.info("Retrying %s with alternate Sony sequence seq=%d",label,self.seq)
   else:
    if result and not result.done():result.set_exception(ConnectionError("no Sony ACK for "+label))
    self.fail("3 missing ACKs for "+label);return
 async def heartbeat(self):
  first=True
  while True:
   await asyncio.sleep(5 if first else 10);first=False
   if not self.linked:continue
   self.volume_reply.clear();await self.send(bytes((0x91,1)),"control heartbeat")
   try:await asyncio.wait_for(self.volume_reply.wait(),10)
   except asyncio.TimeoutError:self.fail("no volume status response to control heartbeat");return
 async def queries(self):
  await self.send(bytes((0x91,1)),"query volume");await self.send(bytes((0x91,0x20,3,0x0F,0xFF,0)),"query subwoofer")
  await self.send(bytes((0x91,0x20,1,0x0F,0xFF,0)),"query night");await self.send(bytes((0x35,0)),"query input")
 def parse(self,payload):
  if not payload:return
  op=payload[0]
  if op in (0x92,0x94) and len(payload)>=3:
   typ=payload[1]
   if typ==1:
    self.bridge.state("volume",payload[2])
    if op==0x92:self.volume_reply.set()
   elif typ==0x12 and len(payload)>=6:
    for pos in range(3,min(len(payload)-2,3+payload[2]*3),3):
     cat=(payload[pos]<<8)|payload[pos+1]
     if cat in MODE_IDS:self.bridge.state("sound_mode",MODE_IDS[cat]);break
   elif typ==0x20 and op==0x92 and len(payload)>=6:
    if payload[2]==1:self.bridge.state("night_mode","ON" if payload[-1] else "OFF")
    elif payload[2]==3:self.subwoofer_reply.set()
  elif op in (0x31,0x36) and len(payload)>=2:
   if payload[1]==0x00:self.bridge.state("input","BT Audio")
   elif payload[1]==0x17:self.bridge.state("input","TV")
   elif payload[1]==0x19:self.bridge.state("input","Analog")
   elif payload[1]==0x18:self.bridge.state("input",self.pending_input if self.pending_input and self.pending_input.startswith("HDMI") else "HDMI 1")
   self.pending_input=None
 async def run(self):
  writer=asyncio.create_task(self.writer());heartbeat=asyncio.create_task(self.heartbeat());self.bridge.handshake_started=self.bridge.loop.time();L.info("Starting persistent Sony session")
  try:
   while True:
    data=await asyncio.to_thread(readfd,self.fd)
    if data is None:continue
    if not data:break
    for typ,seq,payload in self.parser.feed(data):
     if typ==1:
      L.info("RX ACK seq=%d (previous TX seq=%d)",seq,self.seq)
      self.seq=seq;self.ready.set();continue
     if typ!=0:continue
     await asyncio.to_thread(os.write,self.fd,frame(1,seq^1));op=payload[0] if payload else -1
     L.info("RX opcode=0x%02X %s",op,payload.hex(" ").upper());self.parse(payload)
     if op==0 and not self.started:
      self.started=True
      for label,p in startup():await self.send(p,label)
     elif op==3 and not self.linked:
      self.linked=True;self.bridge.handshake_started=None;self.bridge.set_session(self);L.info("Sony control link ready");await self.queries()
  except (OSError,ConnectionError):L.info("RFCOMM closed")
  finally:
   writer.cancel();heartbeat.cancel();await asyncio.gather(writer,heartbeat,return_exceptions=True);self.linked=False;self.bridge.handshake_started=None
   if self.bridge.session is self:self.bridge.set_session(None)
   if not self.closed:
    self.closed=True
    try:os.close(self.fd)
    except OSError:pass
async def main():
 mac=json.loads(Path("/data/options.json").read_text()).get("device_mac","AA:BB:CC:DD:EE:FF").upper()
 bridge=Bridge(asyncio.get_running_loop(),mac);bridge.start()
 bus=await MessageBus(bus_type=BusType.SYSTEM,negotiate_unix_fd=True).connect()
 intro=await bus.introspect("org.bluez","/org/bluez")
 pm=bus.get_proxy_object("org.bluez","/org/bluez",intro).get_interface("org.bluez.ProfileManager1")
 queue=asyncio.Queue();path="/org/ha/sony_ht_ct380/app_server";profile=Profile(queue);bus.export(path,profile)
 await pm.call_register_profile(path,UUID,{"Name":Variant("s","Sony Music Center compatible service"),"Service":Variant("s",UUID),"Channel":Variant("q",11),"Role":Variant("s","server"),"RequireAuthentication":Variant("b",True),"RequireAuthorization":Variant("b",False),"AutoConnect":Variant("b",False)})
 async def find_device():
  root_intro=await bus.introspect("org.bluez","/")
  manager=bus.get_proxy_object("org.bluez","/",root_intro).get_interface("org.freedesktop.DBus.ObjectManager")
  objects=await manager.call_get_managed_objects()
  for object_path,interfaces in objects.items():
   props=interfaces.get("org.bluez.Device1")
   if props and props.get("Address") and props["Address"].value.upper()==mac:
    return object_path,props
  return None,None
 async def device_connected():
  _,props=await find_device()
  return bool(props and props.get("Connected") and props["Connected"].value)
 async def reconnect_control(reason="manual"):
  token=os.getenv("SUPERVISOR_TOKEN","")
  def request_service(service,timeout):
   url=os.getenv("SUPERVISOR_API","http://172.30.32.2")+"/core/api/services/rest_command/"+service
   req=urllib.request.Request(url,data=b"{}",headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},method="POST")
   with urllib.request.urlopen(req,timeout=timeout) as response:
    return response.status,response.read().decode(errors="replace")
  if await device_connected():
   L.info("Reconnect Control (%s): disconnecting Bluetooth before the 10-second reset delay",reason)
   try:
    status,body=await asyncio.to_thread(request_service,"bt_audio_disconnect",25)
    L.info("Reconnect Control: Bluetooth disconnect completed (HTTP %s)",status)
   except (OSError,urllib.error.URLError) as exc:
    L.warning("Reconnect Control: disconnect command failed; continuing with delayed connect: %s",exc)
   await asyncio.sleep(10)
  else:
   L.info("Reconnect Control (%s): Bluetooth is already disconnected",reason)
  for attempt in range(1,4):
   L.info("Reconnect Control: connect attempt %d/3 for %s",attempt,mac)
   try:
    status,body=await asyncio.to_thread(request_service,"bt_audio_connect",40)
    L.info("Reconnect Control: Bluetooth connect request completed (HTTP %s)",status)
   except (OSError,urllib.error.URLError) as exc:
    L.warning("Reconnect Control: Home Assistant connect attempt %d failed: %s",attempt,exc)
   if bridge.session and bridge.session.linked:
    L.info("Reconnect Control: Sony control link recovered during connect attempt")
    return True
   if await device_connected():
    L.info("Reconnect Control: Bluetooth connected on attempt %d; waiting for Sony control",attempt)
    break
   if attempt<3:
    L.warning("Reconnect Control: Bluetooth is still disconnected; waiting 10 seconds before attempt %d",attempt+1)
    await asyncio.sleep(10)
  L.info("Reconnect Control: waiting up to 90 seconds for Sony control")
  deadline=bridge.loop.time()+90
  bluetooth_seen=False
  while bridge.loop.time()<deadline:
   await asyncio.sleep(5)
   if bridge.session and bridge.session.linked:
    L.info("Reconnect Control: Sony control link recovered")
    return True
   if not bluetooth_seen and await device_connected():
    bluetooth_seen=True
    L.info("Reconnect Control: Bluetooth is back; waiting for Sony control handshake")
  if bluetooth_seen:L.error("Reconnect Control: Bluetooth returned but Sony control did not recover within 90 seconds")
  else:L.error("Reconnect Control: Bluetooth Audio Manager did not reconnect within 90 seconds")
  return False
 bridge.reconnect_control=reconnect_control;bridge.device_connected=device_connected
 asyncio.create_task(bridge.recovery_watchdog())
 L.info("Listening on RFCOMM channel 11 for %s",mac)
 while True:
  await Session(await queue.get(),bridge).run();L.info("Waiting for soundbar to reconnect")
asyncio.run(main())
