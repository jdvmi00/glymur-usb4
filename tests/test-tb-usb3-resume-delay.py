#!/usr/bin/env python3
"""Exercise the actual tb_resume_noirq() USB3 re-activation delay.

Resume discovery disables an enabled USB3 downstream adapter also when it
cannot follow the whole path (a dock router that lost its configuration in
sleep) and then returns no tunnel. Re-enabling the adapter before its USB3
link has gone down (40-80 ms measured) loses the tunnelled devices. The model
marks the link down 80 ms after the adapter is disabled."""
from pathlib import Path
import argparse, re, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/thunderbolt/tb.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 m=re.search(r'(?m)^static [^;{}]*?\b'+name+r'\([^;{}]*\)\s*\{',source);assert m,name
 start=m.start();end=m.end();depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
functions='\n'.join(extract(n) for n in ('tb_switch_usb3_enabled','tb_resume_noirq'))
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
struct list_head {struct list_head *next,*prev;};
#define LIST_HEAD(n) struct list_head n={&(n),&(n)}
static void INIT_LIST_HEAD(struct list_head*l){l->next=l->prev=l;}
static void list_add_tail(struct list_head*e,struct list_head*h){e->prev=h->prev;e->next=h;h->prev->next=e;h->prev=e;}
static bool list_empty(const struct list_head*h){return h->next==h;}
#define list_entry(p,t,m) container_of(p,t,m)
#define list_for_each_entry_safe(pos,n,head,member) \
 for(pos=list_entry((head)->next,__typeof__(*pos),member),n=list_entry(pos->member.next,__typeof__(*pos),member);&pos->member!=(head);pos=n,n=list_entry(n->member.next,__typeof__(*n),member))
#define list_for_each_entry_safe_reverse(pos,n,head,member) \
 for(pos=list_entry((head)->prev,__typeof__(*pos),member),n=list_entry(pos->member.prev,__typeof__(*pos),member);&pos->member!=(head);pos=n,n=list_entry(n->member.prev,__typeof__(*n),member))
enum {TB_TYPE_PORT,TB_TYPE_USB3_DOWN,TB_TYPE_USB3_UP,TB_TYPE_DP_IN};
struct tb_switch;
struct tb_port {struct tb_switch *sw;struct tb_port *remote;int type;bool upstream;bool enabled;long disabled_at;bool path_ok;};
struct tb_switch {struct tb_port ports[4];int nports;bool usb4;};
#define tb_switch_for_each_port(sw,p) for((p)=&(sw)->ports[0];(p)<&(sw)->ports[(sw)->nports];(p)++)
struct tb_cm {struct list_head tunnel_list;bool hotplug_active;};
struct tb {struct tb_switch *root_switch;struct tb_cm cm;};
struct tb_tunnel {struct list_head list;bool usb3;struct tb_port *down;bool discovered;};
static struct tb_cm *tb_priv(struct tb*tb){return &tb->cm;}
#define tb_dbg(...) ((void)0)
static bool tb_port_is_usb3_down(const struct tb_port*p){return p&&p->type==TB_TYPE_USB3_DOWN;}
static bool tb_usb3_port_is_enabled(struct tb_port*p){return p->enabled;}
static bool tb_port_has_remote(const struct tb_port*p){return !p->upstream&&p->remote;}
static bool tb_switch_is_usb4(struct tb_switch*sw){return sw->usb4;}
static void tb_switch_reset(struct tb_switch*sw){(void)sw;assert(0);}
static void tb_switch_resume(struct tb_switch*sw,bool r){(void)sw;(void)r;}
static void tb_free_invalid_tunnels(struct tb*tb){(void)tb;}
static void tb_free_unplugged_children(struct tb_switch*sw){(void)sw;}
static void tb_free_unplugged_xdomains(struct tb_switch*sw){(void)sw;}
static void tb_restore_children(struct tb_switch*sw){(void)sw;}
static void tb_switch_enter_redrive(struct tb_switch*sw){(void)sw;}
/* Time in ms; the adapter's USB3 link (ULV) goes down 80 ms after it is disabled. */
static long now;static int usb3_sleeps,lost,activations;
static void msleep(unsigned ms){if(ms==500)usb3_sleeps++;now+=ms;}
static void disable(struct tb_port*p){if(p->enabled){p->enabled=false;p->disabled_at=now;}}
/* Discovery follows every enabled USB3 downstream adapter: a whole path gives a
 * tunnel; a broken one is cleaned up, which disables the adapter, and gives none. */
static struct tb_tunnel found[4];static int nfound;
static void discover(struct tb_switch*sw,struct list_head*list){struct tb_port*p;
 tb_switch_for_each_port(sw,p){
  if(tb_port_is_usb3_down(p)&&p->enabled){if(p->path_ok){struct tb_tunnel*t=&found[nfound++];t->usb3=true;t->down=p;t->discovered=true;list_add_tail(&t->list,list);}else disable(p);}
  if(tb_port_has_remote(p))discover(p->remote->sw,list);}}
static void tb_switch_discover_tunnels(struct tb_switch*sw,struct list_head*list,bool alloc){assert(!alloc);discover(sw,list);}
static void tb_tunnel_deactivate(struct tb_tunnel*t){assert(t->discovered);disable(t->down);}
static void tb_tunnel_put(struct tb_tunnel*t){(void)t;}
static bool tb_tunnel_is_usb3(const struct tb_tunnel*t){return t->usb3;}
static int tb_tunnel_activate(struct tb_tunnel*t){activations++;
 if(t->usb3){if(!t->down->enabled&&now-t->down->disabled_at<80)lost++;t->down->enabled=true;}return 0;}
'''
post=r'''
static struct tb_switch host,dock;static struct tb tb;static struct tb_tunnel ours[2];static int cases;
static void setup(bool host_usb3,bool dock_kept,bool dock_usb3,bool usb3_tunnel){
 memset(&host,0,sizeof(host));memset(&dock,0,sizeof(dock));memset(&tb,0,sizeof(tb));memset(ours,0,sizeof(ours));nfound=0;now=0;usb3_sleeps=lost=activations=0;
 host.usb4=dock.usb4=true;host.nports=3;dock.nports=3;
 host.ports[0]=(struct tb_port){&host,NULL,TB_TYPE_PORT,false,false,0,false};
 host.ports[1]=(struct tb_port){&host,&dock.ports[0],TB_TYPE_PORT,false,false,0,false};
 host.ports[2]=(struct tb_port){&host,NULL,TB_TYPE_USB3_DOWN,false,host_usb3,0,dock_kept};
 dock.ports[0]=(struct tb_port){&dock,&host.ports[1],TB_TYPE_PORT,true,false,0,false};
 dock.ports[1]=(struct tb_port){&dock,NULL,TB_TYPE_USB3_UP,true,true,0,false};
 dock.ports[2]=(struct tb_port){&dock,NULL,TB_TYPE_USB3_DOWN,false,dock_usb3,0,dock_kept};
 /* Adapters already disabled before sleep went down long ago. */
 for(int i=0;i<3;i++){host.ports[i].disabled_at=-1000;dock.ports[i].disabled_at=-1000;}
 tb.root_switch=&host;INIT_LIST_HEAD(&tb.cm.tunnel_list);
 /* The connection manager's own tunnels: USB3 to the dock and DP. */
 ours[0].usb3=usb3_tunnel;ours[0].down=&host.ports[2];list_add_tail(&ours[0].list,&tb.cm.tunnel_list);
 ours[1].usb3=false;list_add_tail(&ours[1].list,&tb.cm.tunnel_list);}
static void resume(void){assert(!tb_resume_noirq(&tb));assert(tb.cm.hotplug_active&&activations==2);}
int main(void){
 /* The dock lost its configuration in sleep (Surface Laptop 8 with the Surface dock): delay. */
 setup(true,false,false,true);resume();assert(usb3_sleeps==1&&!lost&&host.ports[2].enabled);cases++;
 /* Discovery finds the whole USB3 path (the existing upstream case): delay. */
 setup(true,true,false,true);resume();assert(usb3_sleeps==1&&!lost);cases++;
 /* No enabled USB3 adapter before discovery: no delay. */
 setup(false,false,false,true);resume();assert(!usb3_sleeps&&!lost);cases++;
 setup(false,true,false,true);resume();assert(!usb3_sleeps&&!lost);cases++;
 /* An enabled USB3 adapter further down the topology also counts. */
 setup(false,false,true,true);resume();assert(usb3_sleeps==1);cases++;
 /* Without a USB3 tunnel to restore there is nothing to wait for. */
 setup(true,false,false,false);resume();assert(!usb3_sleeps);cases++;
 printf("PASS %d extracted USB3 resume-delay cases\n",cases);
}
'''
FLAGS=['-Wall','-Werror','-Wno-unused-function']
DELAY='\t/* Discovery below tears down any enabled USB3 adapter */\n\tif (tb_switch_usb3_enabled(tb->root_switch))\n\t\tusb3_delay = 500;\n\n'
LOOP='\t\ttb_tunnel_deactivate(tunnel);\n\t\ttb_tunnel_put(tunnel);\n\t}\n'
MUTATIONS=[
 ('upstream_condition',[(DELAY,''),(LOOP.split('\n')[0]+'\n','\t\tif (tb_tunnel_is_usb3(tunnel))\n\t\t\tusb3_delay = 500;\n'+LOOP.split('\n')[0]+'\n')]),
 ('root_switch_only',[('\t\tif (tb_port_has_remote(port) &&\n\t\t    tb_switch_usb3_enabled(port->remote->sw))\n\t\t\treturn true;\n','')]),
 ('disabled_adapter_counts',[('tb_port_is_usb3_down(port) && tb_usb3_port_is_enabled(port)','tb_port_is_usb3_down(port)')]),
 ('checked_after_discovery',[(DELAY,''),(LOOP,LOOP+'\tif (tb_switch_usb3_enabled(tb->root_switch))\n\t\tusb3_delay = 500;\n')]),
]
variants={'correct':functions}
for name,edits in MUTATIONS:
 body=functions
 for old,new in edits:
  assert body.count(old)==1,(name,old)
  body=body.replace(old,new)
 variants[name]=body
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);results={}
 for name,body in variants.items():
  c=d/(name+'.c');exe=d/name;c.write_text(header+body+post)
  flags=FLAGS if name=='correct' else ['-w']
  subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11',*flags,'-fsanitize=address,undefined','-g',str(c),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
  if name=='correct':assert r.returncode==0,r.stderr;print(r.stdout.strip());results[name]='pass'
  else:assert body!=functions and r.returncode==134,(name,r.returncode,r.stderr[-300:]);results[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'variants':results},indent=2)+'\n')
 print(results)
