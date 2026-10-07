#!/usr/bin/env python3
"""Exercise the actual usb_enable_lpm() on native and USB4-tunnelled USB3 links.

USB4 v2.0 section 9.2.1.1: the internal USB3 port behind a USB4 adapter does
not support U1. Hub-initiated U1 must be skipped on a tunnelled link without
suppressing U2, which the link can enter and leave once DEPOCHANGE is clear."""
from pathlib import Path
import argparse, re, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/usb/core/hub.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
m=re.search(r'(?m)^void usb_enable_lpm\(struct usb_device \*udev\)\n\{',source);assert m
end=m.end();depth=1
while depth:
 depth+=(source[end]=='{')-(source[end]=='}');end+=1
function=source[m.start():end]
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
enum usb_device_speed {USB_SPEED_HIGH=3,USB_SPEED_SUPER=5,USB_SPEED_SUPER_PLUS=6};
enum usb_device_state {USB_STATE_ADDRESS=6,USB_STATE_CONFIGURED=7};
enum usb3_link_state {USB3_LPM_U0,USB3_LPM_U1,USB3_LPM_U2,USB3_LPM_U3};
enum usb_link_tunnel_mode {USB_LINK_UNKNOWN,USB_LINK_NATIVE,USB_LINK_TUNNELED};
struct usb_bus {int unused;};
struct usb_hcd;
struct hc_driver {int (*enable_usb3_lpm_timeout)(struct usb_hcd*,void*,int);int (*disable_usb3_lpm_timeout)(struct usb_hcd*,void*,int);};
struct usb_hcd {const struct hc_driver *driver;};
struct usb_port {bool usb3_lpm_u1_permit,usb3_lpm_u2_permit;};
struct usb_hub {struct usb_port *ports[1];};
struct usb_device {struct usb_device *parent;enum usb_device_speed speed;bool lpm_capable;enum usb_device_state state;int lpm_disable_count;
 struct usb_bus *bus;int portnum;enum usb_link_tunnel_mode tunnel_mode;bool usb3_lpm_u1_enabled,usb3_lpm_u2_enabled;};
static int dummy(struct usb_hcd*h,void*u,int s){(void)h;(void)u;(void)s;return 1;}
static const struct hc_driver drv={dummy,dummy};
static struct usb_hcd hcd={&drv};static struct usb_port port;static struct usb_hub hub={{&port}};static struct usb_device root;
static bool fail_u2,may[4];static int dev_init[4],hub_init[4];
static struct usb_hcd *bus_to_hcd(struct usb_bus*b){(void)b;return &hcd;}
static struct usb_hub *usb_hub_to_struct_hub(struct usb_device*d){assert(d==&root);return &hub;}
/* Hub-initiated LPM: the host programs the timeout and the parent port. */
static int usb_enable_link_state(struct usb_hcd*h,struct usb_device*u,enum usb3_link_state s){assert(h==&hcd);
 if(s==USB3_LPM_U2&&fail_u2)return -EBUSY;
 hub_init[s]++;
 if(s==USB3_LPM_U1)u->usb3_lpm_u1_enabled=1;else u->usb3_lpm_u2_enabled=1;
 return 0;}
static bool usb_device_may_initiate_lpm(struct usb_device*u,enum usb3_link_state s){(void)u;return may[s];}
static int usb_set_device_initiated_lpm(struct usb_device*u,enum usb3_link_state s,bool en){(void)u;assert(en);dev_init[s]++;return 0;}
'''
post=r'''
static struct usb_bus bus;static struct usb_device udev;static int cases;
static void setup(enum usb_link_tunnel_mode mode,bool u1,bool u2,bool may1,bool may2){
 memset(&udev,0,sizeof(udev));udev.parent=&root;udev.speed=USB_SPEED_SUPER_PLUS;udev.lpm_capable=true;udev.state=USB_STATE_CONFIGURED;
 udev.lpm_disable_count=1;udev.bus=&bus;udev.portnum=1;udev.tunnel_mode=mode;port.usb3_lpm_u1_permit=u1;port.usb3_lpm_u2_permit=u2;
 may[USB3_LPM_U1]=may1;may[USB3_LPM_U2]=may2;fail_u2=false;memset(dev_init,0,sizeof(dev_init));memset(hub_init,0,sizeof(hub_init));}
int main(void){
 enum usb_link_tunnel_mode modes[]={USB_LINK_UNKNOWN,USB_LINK_NATIVE,USB_LINK_TUNNELED};
 for(int m=0;m<3;m++)for(int u1=0;u1<2;u1++)for(int u2=0;u2<2;u2++)for(int d1=0;d1<2;d1++)for(int d2=0;d2<2;d2++){
  bool tunneled=modes[m]==USB_LINK_TUNNELED;
  setup(modes[m],u1,u2,d1,d2);usb_enable_lpm(&udev);assert(!udev.lpm_disable_count);
  /* Hub-initiated U1 only where permitted and never on a tunnelled link; U2 wherever permitted. */
  assert(hub_init[USB3_LPM_U1]==(u1&&!tunneled)&&udev.usb3_lpm_u1_enabled==(u1&&!tunneled));
  assert(hub_init[USB3_LPM_U2]==u2&&udev.usb3_lpm_u2_enabled==u2);
  /* Device-initiated U2 on a tunnelled link whenever hub-initiated U2 is on and the device may initiate it. */
  if(tunneled&&u2&&d2)assert(dev_init[USB3_LPM_U2]==1);
  /* Native links keep the upstream device-initiated policy. */
  if(!tunneled)assert(dev_init[USB3_LPM_U1]==d1&&dev_init[USB3_LPM_U2]==(d1&&d2));
  cases++;
 }
 /* A failed hub-initiated U2 stops there, as upstream does for U1 and U2. */
 setup(USB_LINK_TUNNELED,true,true,true,true);fail_u2=true;usb_enable_lpm(&udev);
 assert(!hub_init[USB3_LPM_U1]&&!udev.usb3_lpm_u2_enabled&&!dev_init[USB3_LPM_U1]&&!dev_init[USB3_LPM_U2]);cases++;
 /* Below SuperSpeed or still unconfigured: nothing. */
 setup(USB_LINK_TUNNELED,true,true,true,true);udev.speed=USB_SPEED_HIGH;usb_enable_lpm(&udev);assert(!hub_init[USB3_LPM_U2]&&udev.lpm_disable_count==1);cases++;
 setup(USB_LINK_TUNNELED,true,true,true,true);udev.state=USB_STATE_ADDRESS;usb_enable_lpm(&udev);assert(!hub_init[USB3_LPM_U2]);cases++;
 printf("PASS %d extracted USB3 link power cases\n",cases);
}
'''
FLAGS=['-Wall','-Werror','-Wno-unused-function']
MUTATIONS=[
 ('u1_on_tunnel','if (port_dev->usb3_lpm_u1_permit && !tunneled)','if (port_dev->usb3_lpm_u1_permit)'),
 ('u1_skip_stops_u2','if (port_dev->usb3_lpm_u1_permit && !tunneled)\n\t\tif (usb_enable_link_state(hcd, udev, USB3_LPM_U1))',
  'if (port_dev->usb3_lpm_u1_permit)\n\t\tif (tunneled || usb_enable_link_state(hcd, udev, USB3_LPM_U1))'),
 ('no_tunnel_device_u2','\t} else if (tunneled && udev->usb3_lpm_u2_enabled &&\n\t\t   usb_device_may_initiate_lpm(udev, USB3_LPM_U2)) {\n\t\tusb_set_device_initiated_lpm(udev, USB3_LPM_U2, true);\n\t}','\t}'),
 ('native_treated_as_tunnel','tunneled = udev->tunnel_mode == USB_LINK_TUNNELED;','tunneled = udev->tunnel_mode != USB_LINK_TUNNELED;'),
]
variants={'correct':function}
for name,old,new in MUTATIONS:
 assert function.count(old)==1,name
 variants[name]=function.replace(old,new)
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);results={}
 for name,body in variants.items():
  c=d/(name+'.c');exe=d/name;c.write_text(header+body+post)
  flags=FLAGS if name=='correct' else ['-w']
  subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11',*flags,'-fsanitize=address,undefined','-g',str(c),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
  if name=='correct':assert r.returncode==0,r.stderr;print(r.stdout.strip());results[name]='pass'
  else:assert body!=function and r.returncode==134,(name,r.returncode,r.stderr[-300:]);results[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'variants':results},indent=2)+'\n')
 print(results)
