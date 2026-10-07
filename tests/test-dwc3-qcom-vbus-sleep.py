#!/usr/bin/env python3
"""Exercise the actual dwc3-qcom role-switch VBUS override around system suspend.

UCSI can switch the USB role while the system is suspending (a cable removed
during s2idle). The glue clocks are gated by then, and an access to QSCRATCH
without them stalls the SoC. The override must be deferred to resume and give
the same register values as an immediate write would."""
from pathlib import Path
import argparse, re, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/usb/dwc3/dwc3-qcom.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 m=re.search(r'(?m)^static [^;{}]*?\b'+name+r'\([^;{}]*\)\s*\{',source);assert m,name
 start=m.start();end=m.end();depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
functions='\n'.join(extract(n) for n in ('dwc3_qcom_setbits','dwc3_qcom_clrbits','dwc3_qcom_vbus_override_enable',
 'dwc3_qcom_suspend','dwc3_qcom_resume','dwc3_qcom_set_role_notifier'))
DEFINES=('QSCRATCH_HS_PHY_CTRL','UTMI_OTG_VBUS_VALID','SW_SESSVLD_SEL','QSCRATCH_SS_PHY_CTRL','LANE0_PWR_PRESENT',
 'PWR_EVNT_LPM_IN_L2_MASK','PWR_EVNT_LPM_OUT_L2_MASK','DWC3_QCOM_MAX_PORTS')
defines='\n'.join(re.search(r'(?m)^#define '+n+r'\s.*$',source)[0] for n in DEFINES)
table=re.search(r'(?ms)^static const u32 pwr_evnt_irq_stat_reg\[DWC3_QCOM_MAX_PORTS\] = \{.*?\};',source)[0]
assert 'mutex_init(&qcom->vbus_lock);' in extract('dwc3_qcom_probe')
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define __iomem
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
'''+defines+'\n'+table+r'''
enum usb_role {USB_ROLE_NONE,USB_ROLE_HOST,USB_ROLE_DEVICE};
enum usb_device_speed {USB_SPEED_UNKNOWN};
struct mutex {int held;};
struct device {int unused;};
struct clk_bulk_data {int unused;};
struct dwc3 {void *xhci;};
struct dwc3_qcom_port {enum usb_device_speed usb2_speed;};
struct dwc3_qcom {
 struct device *dev;struct dwc3 dwc;unsigned char *qscratch_base;int num_ports;struct dwc3_qcom_port ports[DWC3_QCOM_MAX_PORTS];
 int num_clocks;struct clk_bulk_data *clks;bool is_suspended;enum usb_role current_role;
 struct mutex vbus_lock;bool vbus_override_pending;bool vbus_override;
};
#define to_dwc3_qcom(d) container_of((d),struct dwc3_qcom,dwc)
static struct dwc3_qcom qcom;static struct device dev;
static unsigned char regs[0x400];static bool clocks_on;static int clk_error,rpm_error,refs,seq,vbus_seq,evnt_seq,writes;
static bool runtime_suspended;
static void mutex_lock(struct mutex*m){assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex*m){assert(m->held);m->held=0;}
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_dbg(...) ((void)0)
/* Glue registers need the glue clocks; without them the access stalls. */
static unsigned off_of(const volatile void*a){unsigned o=(unsigned)((const unsigned char*)a-regs);assert(o+4<=sizeof(regs));return o;}
static u32 readl(const volatile void*a){assert(clocks_on);u32 v;memcpy(&v,regs+off_of(a),4);return v;}
static void writel(u32 v,volatile void*a){unsigned o=off_of(a);assert(clocks_on);memcpy(regs+o,&v,4);writes++;seq++;
 if(o==QSCRATCH_SS_PHY_CTRL||o==QSCRATCH_HS_PHY_CTRL)vbus_seq=seq;else if(o==pwr_evnt_irq_stat_reg[0]&&!evnt_seq)evnt_seq=seq;}
static int clk_bulk_prepare_enable(int n,struct clk_bulk_data*c){(void)n;(void)c;if(clk_error)return clk_error;clocks_on=true;return 0;}
static void clk_bulk_disable_unprepare(int n,struct clk_bulk_data*c){(void)n;(void)c;clocks_on=false;}
static int dwc3_qcom_interconnect_enable(struct dwc3_qcom*q){(void)q;return 0;}
static int dwc3_qcom_interconnect_disable(struct dwc3_qcom*q){(void)q;return 0;}
static bool dwc3_qcom_is_host(struct dwc3_qcom*q){return q->dwc.xhci;}
static enum usb_device_speed dwc3_qcom_read_usb2_speed(struct dwc3_qcom*q,int i){(void)q;(void)i;return USB_SPEED_UNKNOWN;}
static void dwc3_qcom_enable_interrupts(struct dwc3_qcom*q){(void)q;}
static void dwc3_qcom_disable_interrupts(struct dwc3_qcom*q){(void)q;}
static int dwc3_qcom_resume(struct dwc3_qcom *qcom, bool wakeup);
/* Runtime PM: a runtime-suspended glue is resumed; a runtime-active glue is
 * not, even while system suspend has gated its clocks. */
static int pm_runtime_resume_and_get(struct device*d){assert(d==&dev);if(rpm_error)return rpm_error;
 if(runtime_suspended){assert(!dwc3_qcom_resume(&qcom,true));runtime_suspended=false;}refs++;return 0;}
static void pm_runtime_mark_last_busy(struct device*d){(void)d;}
static void pm_runtime_put_sync(struct device*d){assert(d==&dev&&refs>0);refs--;}
'''
post=r'''
static int cases;
static void reset(enum usb_role role){memset(&qcom,0,sizeof(qcom));memset(regs,0,sizeof(regs));qcom.dev=&dev;qcom.qscratch_base=regs;qcom.num_ports=2;
 qcom.dwc.xhci=&qcom;qcom.current_role=role;clocks_on=true;clk_error=rpm_error=refs=seq=vbus_seq=evnt_seq=writes=0;runtime_suspended=false;}
static void role(enum usb_role r){dwc3_qcom_set_role_notifier(&qcom.dwc,r);assert(!qcom.vbus_lock.held&&!refs&&qcom.current_role==r);}
static void sys_suspend(void){assert(!dwc3_qcom_suspend(&qcom,true));assert(qcom.is_suspended&&!clocks_on&&!qcom.vbus_lock.held);}
static void sys_resume(void){seq=vbus_seq=evnt_seq=0;assert(!dwc3_qcom_resume(&qcom,true));assert(!qcom.is_suspended&&clocks_on&&!qcom.vbus_lock.held);}
static u32 ss(void){u32 v;memcpy(&v,regs+QSCRATCH_SS_PHY_CTRL,4);return v;}
static u32 hs(void){u32 v;memcpy(&v,regs+QSCRATCH_HS_PHY_CTRL,4);return v;}
/* The override that the stock code writes immediately for a switch away from @from. */
static void expect(enum usb_role from){bool on=from!=USB_ROLE_DEVICE;
 assert(!!(ss()&LANE0_PWR_PRESENT)==on);assert(((hs()&(UTMI_OTG_VBUS_VALID|SW_SESSVLD_SEL))==(UTMI_OTG_VBUS_VALID|SW_SESSVLD_SEL))==on);
 assert(!(hs()&(UTMI_OTG_VBUS_VALID|SW_SESSVLD_SEL))||on);}
int main(void){
 enum usb_role all[]={USB_ROLE_NONE,USB_ROLE_HOST,USB_ROLE_DEVICE};
 /* Awake: every role switch writes the override at once, as before. */
 for(int a=0;a<3;a++)for(int b=0;b<3;b++){if(a==b)continue;reset(all[a]);role(all[b]);expect(all[a]);assert(!qcom.vbus_override_pending);cases++;}
 /* Same role: nothing happens. */
 reset(USB_ROLE_HOST);role(USB_ROLE_HOST);assert(!writes);cases++;
 /* Cable removed while suspended: no register access until resume, then the same value, before the L2 event clear. */
 for(int a=0;a<3;a++)for(int b=0;b<3;b++){if(a==b)continue;
  reset(all[a]);sys_suspend();writes=0;role(all[b]);assert(!writes&&qcom.vbus_override_pending);
  sys_resume();expect(all[a]);assert(!qcom.vbus_override_pending&&vbus_seq&&evnt_seq&&vbus_seq<evnt_seq);cases++;}
 /* Unplug and replug during one sleep: the last switch wins. */
 reset(USB_ROLE_HOST);sys_suspend();role(USB_ROLE_NONE);role(USB_ROLE_DEVICE);sys_resume();expect(USB_ROLE_NONE);cases++;
 reset(USB_ROLE_DEVICE);sys_suspend();role(USB_ROLE_NONE);role(USB_ROLE_HOST);sys_resume();expect(USB_ROLE_NONE);cases++;
 /* A failed resume keeps the request and releases the lock; the next resume applies it. */
 reset(USB_ROLE_HOST);sys_suspend();role(USB_ROLE_NONE);clk_error=-EIO;assert(dwc3_qcom_resume(&qcom,true)==-EIO);
 assert(qcom.is_suspended&&!clocks_on&&qcom.vbus_override_pending&&!qcom.vbus_lock.held);clk_error=0;sys_resume();expect(USB_ROLE_HOST);cases++;
 /* An applied request is not applied again at a later resume. */
 reset(USB_ROLE_DEVICE);sys_suspend();role(USB_ROLE_HOST);sys_resume();expect(USB_ROLE_DEVICE);
 role(USB_ROLE_NONE);expect(USB_ROLE_HOST);sys_suspend();sys_resume();expect(USB_ROLE_HOST);cases++;
 /* A runtime-suspended glue is resumed by runtime PM and written at once. */
 reset(USB_ROLE_HOST);sys_suspend();runtime_suspended=true;role(USB_ROLE_NONE);assert(!qcom.is_suspended&&!qcom.vbus_override_pending);expect(USB_ROLE_HOST);cases++;
 /* A failed runtime resume changes nothing. */
 reset(USB_ROLE_HOST);rpm_error=-EIO;dwc3_qcom_set_role_notifier(&qcom.dwc,USB_ROLE_NONE);assert(!writes&&qcom.current_role==USB_ROLE_HOST);cases++;
 printf("PASS %d extracted dwc3-qcom VBUS override cases\n",cases);
}
'''
FLAGS=['-Wall','-Werror','-Wno-unused-function']
MUTATIONS=[
 ('write_while_suspended','\tif (qcom->is_suspended) {\n\t\tqcom->vbus_override = qcom->current_role != USB_ROLE_DEVICE;\n\t\tqcom->vbus_override_pending = true;\n\t} else {\n\t\tdwc3_qcom_vbus_override_enable(qcom, qcom->current_role != USB_ROLE_DEVICE);\n\t}',
  '\tdwc3_qcom_vbus_override_enable(qcom, qcom->current_role != USB_ROLE_DEVICE);'),
 ('pending_never_applied','\tif (qcom->vbus_override_pending) {\n\t\tdwc3_qcom_vbus_override_enable(qcom, qcom->vbus_override);\n\t\tqcom->vbus_override_pending = false;\n\t}\n',''),
 ('pending_before_clocks','\tmutex_lock(&qcom->vbus_lock);\n\tret = clk_bulk_prepare_enable',
  '\tmutex_lock(&qcom->vbus_lock);\n\tif (qcom->vbus_override_pending)\n\t\tdwc3_qcom_vbus_override_enable(qcom, qcom->vbus_override);\n\tret = clk_bulk_prepare_enable'),
 ('pending_not_cleared','\t\tqcom->vbus_override_pending = false;\n',''),
 ('lock_kept_on_resume_error','\tif (ret < 0) {\n\t\tmutex_unlock(&qcom->vbus_lock);\n\t\treturn ret;\n\t}','\tif (ret < 0)\n\t\treturn ret;'),
]
variants={'correct':functions}
for name,old,new in MUTATIONS:
 assert functions.count(old)==1,name
 variants[name]=functions.replace(old,new)
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
