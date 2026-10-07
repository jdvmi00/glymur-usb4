#!/usr/bin/env python3
"""Exercise the actual combo PHY Type-C mode handling while USB4 owns the PHY, phy_exit(usb4)
and the USB4 clamp across system sleep."""
from pathlib import Path
import argparse, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/phy/qualcomm/phy-qcom-qmp-combo.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 start=source.rfind('static ',0,source.index(name+'(')); brace=source.index('{',start);end=brace+1;depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
functions='\n'.join(extract(n) for n in ('qmp_combo_usb4_exit','qmp_combo_typec_mux_set','qmp_combo_suspend','qmp_combo_resume'))
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#define USB_TYPEC_DP_SID 0xff01
#define USB_TYPEC_TBT_SID 0x8087
enum {TYPEC_STATE_SAFE,TYPEC_STATE_USB,TYPEC_STATE_MODAL};
#define TYPEC_MODE_USB4 4
enum {TYPEC_DP_STATE_A=TYPEC_STATE_MODAL,TYPEC_DP_STATE_B,TYPEC_DP_STATE_C,TYPEC_DP_STATE_D,TYPEC_DP_STATE_E,TYPEC_DP_STATE_F};
enum qmpphy_mode {QMPPHY_MODE_USB3DP=0,QMPPHY_MODE_DP_ONLY,QMPPHY_MODE_USB3_ONLY,QMPPHY_MODE_USB4};
enum {QPHY_PCS_USB4_CLAMP_ENABLE,QPHY_USB4_AON_TOGGLE_ENABLE,QPHY_LAYOUT_SIZE};
struct qmp_phy_cfg {unsigned int regs[QPHY_LAYOUT_SIZE];};
#define CLAMP_EN 0x1
#define __maybe_unused __attribute__((unused))
struct mutex {int held;};
struct clk {int enabled;};
struct device {int unused;};
struct phy {void *drvdata;};
struct typec_altmode {unsigned short svid;};
struct typec_mux_state {struct typec_altmode *alt;unsigned long mode;void *data;};
struct typec_mux_dev {void *drvdata;};
struct qmp_combo {
 struct device *dev;const struct qmp_phy_cfg *cfg;unsigned char *pcs_aon;struct mutex phy_mutex;int init_count;enum qmpphy_mode qmpphy_mode;
 struct phy *usb_phy;unsigned int usb_init_count;unsigned int dp_init_count;bool dp_powered_on;
 unsigned int usb4_init_count;enum qmpphy_mode typec_mode;bool typec_mode_pending;bool com_powered_on;
 struct clk *p2rr2p_pipe_clk;
};
static int reconfigures,reconfigure_error;static enum qmpphy_mode reconfigured_to;
static void guard_mutex(struct mutex*m){m->held=1;}
#define guard(t) guard_##t
#define dev_dbg(...) ((void)0)
#define dev_err(...) ((void)0)
static void *phy_get_drvdata(struct phy*p){return p->drvdata;}
static struct qmp_combo qmp;
static void *dev_get_drvdata(struct device*d){(void)d;return &qmp;}
/* Always-on PCS writes: the USB4 toggle (0x0c) and the USB4 clamp (0x04). */
static int toggle_writes,clamp_writes;
static void aon_write(unsigned char*base,unsigned int off,unsigned int bits){assert(base&&qmp.phy_mutex.held&&bits==1&&(off==0x0c||off==0x04));if(off==0x0c)toggle_writes++;else clamp_writes++;}
static void qphy_setbits(unsigned char*base,unsigned int off,unsigned int bits){aon_write(base,off,bits);base[off]|=bits;}
static void qphy_clrbits(unsigned char*base,unsigned int off,unsigned int bits){aon_write(base,off,bits);base[off]&=~bits;}
static void *typec_mux_get_drvdata(struct typec_mux_dev*m){return m->drvdata;}
static void clk_disable_unprepare(struct clk*c){assert(c->enabled);c->enabled=0;}
static int qmp_combo_usb_power_off(struct phy*p){(void)p;return 0;}
/* The always-on USB4 toggle must be back under hardware control before the PHY powers down. */
static int qmp_combo_com_exit(struct qmp_combo*q,bool force){assert(!force);assert(!q->pcs_aon||q->pcs_aon[0x0c]==1);if(--q->init_count)return 0;q->com_powered_on=false;return 0;}
static int qmp_combo_reconfigure_phy(struct qmp_combo*q,enum qmpphy_mode m){assert(q->phy_mutex.held&&!q->usb4_init_count);reconfigures++;reconfigured_to=m;if(reconfigure_error)return reconfigure_error;q->qmpphy_mode=m;q->com_powered_on=true;return 0;}
'''
post=r'''
static struct clk p2r;static const struct qmp_phy_cfg v8={{[QPHY_PCS_USB4_CLAMP_ENABLE]=0x04,[QPHY_USB4_AON_TOGGLE_ENABLE]=0x0c}};static unsigned char aon[0x40];
static struct device pdev;static struct phy usb4phy={&qmp},usbphy={&qmp};static struct typec_mux_dev mux={&qmp};
static struct typec_altmode dpalt={USB_TYPEC_DP_SID},tbt={USB_TYPEC_TBT_SID};static int cases;
/* USB4 owns the PHY; dwc3 (and optionally DP) hold their own common references. */
static void owned(int consumers){memset(&qmp,0,sizeof(qmp));qmp.usb_phy=&usbphy;qmp.p2rr2p_pipe_clk=&p2r;p2r.enabled=1;qmp.usb4_init_count=1;qmp.usb_init_count=consumers>0;qmp.init_count=1+consumers;qmp.qmpphy_mode=QMPPHY_MODE_USB4;qmp.com_powered_on=true;reconfigures=reconfigure_error=0;
 qmp.cfg=&v8;qmp.pcs_aon=aon;memset(aon,0,sizeof(aon));aon[0x04]=1;toggle_writes=clamp_writes=0;}
static void set(struct typec_altmode*alt,unsigned long mode){struct typec_mux_state s={alt,mode,NULL};qmp.phy_mutex.held=0;assert(!qmp_combo_typec_mux_set(&mux,&s));}
static void usb4_exit(void){qmp.phy_mutex.held=0;assert(!qmp_combo_usb4_exit(&usb4phy));assert(!p2r.enabled&&!qmp.usb4_init_count);assert(toggle_writes==1&&aon[0x0c]==1);}
static void sleep_cycle(void){qmp.phy_mutex.held=0;assert(!qmp_combo_suspend(&pdev));qmp.phy_mutex.held=0;assert(!qmp_combo_resume(&pdev));}
int main(void){
 /* HDMI cable: requests while USB4 owns the PHY do not touch it; phy_exit applies DP-only. */
 owned(1);set(NULL,TYPEC_STATE_USB);set(&dpalt,TYPEC_DP_STATE_C);set(&dpalt,TYPEC_DP_STATE_C);
 assert(!reconfigures&&qmp.qmpphy_mode==QMPPHY_MODE_USB4&&qmp.typec_mode_pending);
 usb4_exit();assert(reconfigures==1&&reconfigured_to==QMPPHY_MODE_DP_ONLY&&!qmp.typec_mode_pending);cases++;
 /* The latest request wins: a Dell replay ends in USB4 entry, which records nothing. */
 owned(1);set(&dpalt,TYPEC_DP_STATE_D);set(NULL,TYPEC_STATE_SAFE);set(NULL,TYPEC_STATE_USB);set(NULL,TYPEC_MODE_USB4);set(&tbt,TYPEC_STATE_MODAL);
 usb4_exit();assert(reconfigures==1&&reconfigured_to==QMPPHY_MODE_USB3_ONLY);cases++;
 for(int pin=TYPEC_DP_STATE_A;pin<=TYPEC_DP_STATE_F;pin++){
  owned(1);set(&dpalt,pin);usb4_exit();
  assert(reconfigures==1&&reconfigured_to==((pin==TYPEC_DP_STATE_C||pin==TYPEC_DP_STATE_E)?QMPPHY_MODE_DP_ONLY:QMPPHY_MODE_USB3DP));cases++;
 }
 /* No request while owned: keep the upstream wait-for-mux_set behavior. */
 owned(1);usb4_exit();assert(!reconfigures&&qmp.qmpphy_mode==QMPPHY_MODE_USB4);cases++;
 /* No other consumer: nothing to power; the next consumer starts in the requested mode. */
 owned(0);set(&dpalt,TYPEC_DP_STATE_C);usb4_exit();assert(!reconfigures&&qmp.qmpphy_mode==QMPPHY_MODE_DP_ONLY&&!qmp.typec_mode_pending);cases++;
 /* A DP PHY still powered delays the switch, as mux_set does. */
 owned(1);qmp.dp_powered_on=true;set(&dpalt,TYPEC_DP_STATE_C);usb4_exit();assert(!reconfigures);cases++;
 /* A reconfiguration failure does not fail phy_exit and is not retried later. */
 owned(1);set(&dpalt,TYPEC_DP_STATE_C);reconfigure_error=-ETIMEDOUT;usb4_exit();assert(reconfigures==1&&!qmp.typec_mode_pending);cases++;
 /* Without USB4 ownership mux_set reconfigures directly and clears a stale record. */
 owned(1);qmp.usb4_init_count=0;qmp.init_count=1;qmp.qmpphy_mode=QMPPHY_MODE_USB3_ONLY;qmp.typec_mode_pending=true;set(&dpalt,TYPEC_DP_STATE_C);
 assert(reconfigures==1&&reconfigured_to==QMPPHY_MODE_DP_ONLY&&!qmp.typec_mode_pending);cases++;
 /* A PHY without an always-on block (other SoCs) is left alone. */
 owned(1);qmp.pcs_aon=NULL;qmp.phy_mutex.held=0;assert(!qmp_combo_usb4_exit(&usb4phy));assert(!toggle_writes);cases++;
 /* System sleep with USB4 owning the PHY: clamp at suspend, release at resume. */
 owned(1);qmp.phy_mutex.held=0;assert(!qmp_combo_suspend(&pdev));assert(clamp_writes==1&&aon[0x04]==0);
 qmp.phy_mutex.held=0;assert(!qmp_combo_resume(&pdev));assert(clamp_writes==2&&aon[0x04]==1);cases++;
 /* Without USB4 (native USB3/DP or idle) or without an always-on block, sleep writes nothing. */
 owned(1);qmp.usb4_init_count=0;sleep_cycle();assert(!clamp_writes&&aon[0x04]==1);cases++;
 owned(1);qmp.pcs_aon=NULL;sleep_cycle();assert(!clamp_writes);cases++;
 printf("PASS %d extracted PHY Type-C mode, exit and sleep cases\n",cases);
}
'''
FLAGS=['-Wall', '-Werror', '-Wno-unused-function']
MUTATIONS=[
 ('reconfigure_while_owned','if (qmp->usb4_init_count) {','if (0) {'),
 ('exit_drops_request','if (!qmp->typec_mode_pending)\n\t\treturn 0;','if (1)\n\t\treturn 0;'),
 ('exit_keeps_request','qmp->typec_mode_pending = false;\n\n\tif (!qmp->init_count)','if (!qmp->init_count)'),
 ('unused_phy_forgets_mode','qmp->qmpphy_mode = qmp->typec_mode;\n\t\treturn 0;','return 0;'),
 ('switch_under_powered_dp','if (qmp->dp_powered_on) {','if (0) {'),
 ('stale_request_kept','\tqmp->typec_mode_pending = false;\n\n\tif (new_mode ==','\n\tif (new_mode =='),
 ('no_aon_toggle_restore','qphy_setbits(qmp->pcs_aon, qmp->cfg->regs[QPHY_USB4_AON_TOGGLE_ENABLE], 0x1);',';'),
 ('aon_toggle_after_power_down','\tif (qmp->pcs_aon && qmp->cfg->regs[QPHY_USB4_AON_TOGGLE_ENABLE])\n\t\tqphy_setbits(qmp->pcs_aon, qmp->cfg->regs[QPHY_USB4_AON_TOGGLE_ENABLE], 0x1);\n\n\tret = qmp_combo_com_exit(qmp, false);','\tret = qmp_combo_com_exit(qmp, false);\n\tif (qmp->pcs_aon && qmp->cfg->regs[QPHY_USB4_AON_TOGGLE_ENABLE])\n\t\tqphy_setbits(qmp->pcs_aon, qmp->cfg->regs[QPHY_USB4_AON_TOGGLE_ENABLE], 0x1);'),
 ('clamp_without_usb4','if (qmp->usb4_init_count && qmp->pcs_aon &&\n\t    qmp->cfg->regs[QPHY_PCS_USB4_CLAMP_ENABLE])\n\t\tqphy_clrbits','if (qmp->pcs_aon &&\n\t    qmp->cfg->regs[QPHY_PCS_USB4_CLAMP_ENABLE])\n\t\tqphy_clrbits'),
 ('clamp_kept_after_resume','\t\tqphy_setbits(qmp->pcs_aon, qmp->cfg->regs[QPHY_PCS_USB4_CLAMP_ENABLE],\n\t\t\t     CLAMP_EN);','\t\t;'),
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
  else:assert body!=functions and r.returncode==134,(name,r.returncode);results[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'variants':results},indent=2)+'\n')
 print(results)
