#!/usr/bin/env python3
"""Exercise actual IRQ/clock functions, including queued ISR and clock failures."""
from pathlib import Path
import argparse, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 start=source.rfind('static ',0,source.index(name+'(')); brace=source.index('{',start);end=brace+1;depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
names=('msm_dp_ctrl_link_irq_mask','msm_dp_ctrl_get_interrupt','msm_dp_ctrl_usb4_clk_sel_restore','msm_dp_ctrl_link_clk_enable','msm_dp_ctrl_link_clk_disable')
functions='\n'.join(extract(n) for n in names)
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
#define REG_DP_INTR_STATUS2 0x24
#define DP_INTERRUPT_STATUS2 0x249
#define DP_INTERRUPT_STATUS_ACK_SHIFT 1
#define DP_INTERRUPT_STATUS2_ACK (0x249<<1)
#define DP_INTERRUPT_STATUS2_MASK (0x249<<2)
#define REG_DP_USB4_CLK_SEL 0xf8
#define DP_USB4_CLK_SEL_NATIVE BIT(0)
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
#define dev_info(...) ((void)0)
#define drm_dbg_dp(...) ((void)0)
#define spin_lock_irqsave(l,f) do{assert(!*(l));*(l)=1;(f)=0;}while(0)
#define spin_unlock_irqrestore(l,f) do{assert(*(l));assert((f)==0);*(l)=0;}while(0)
struct msm_dp_ctrl {int unused;};
struct msm_dp_ctrl_private {
 struct msm_dp_ctrl msm_dp_ctrl;
 bool core_clks_on,link_clks_on,dpin_clk_on,usb4_clk_sel_saved,usb4_link_clk_on;
 u32 usb4_clk_sel_native;
 void *aux,*dpin_clk,*usb4_link_clk,*link_clks,*dev,*drm_dev;
 int num_link_clks,link_irq_lock;
};
static bool attached,clocked;
static u32 irq,selector;
static int fault,router_count,dpin_count;
static bool msm_dp_aux_usb4_attached(void *p){(void)p;return attached;}
static u32 msm_dp_read_ahb(struct msm_dp_ctrl_private*c,int r){
 assert(c->core_clks_on);if(r==0x24){assert(c->link_irq_lock);return irq;}assert(r==0xf8);return selector;
}
static void msm_dp_write_ahb(struct msm_dp_ctrl_private*c,int r,u32 v){
 assert(c->core_clks_on);if(r==0x24){assert(c->link_irq_lock);
  u32 status=irq&DP_INTERRUPT_STATUS2;
  if(clocked)status&=~((v>>1)&DP_INTERRUPT_STATUS2);
  irq=status|(v&DP_INTERRUPT_STATUS2_MASK);return;}
 assert(r==0xf8);selector=v;
}
static int msm_dp_ctrl_core_clk_enable(struct msm_dp_ctrl*p){
 struct msm_dp_ctrl_private*c=container_of(p,struct msm_dp_ctrl_private,msm_dp_ctrl);
 if(fault==1)return -EIO;c->core_clks_on=true;return 0;
}
static int clk_bulk_prepare_enable(int n,void*p){(void)n;(void)p;if(attached)assert(!(irq&DP_INTERRUPT_STATUS2_MASK));if(fault==2)return -EIO;clocked=true;return 0;}
static void clk_bulk_disable_unprepare(int n,void*p){(void)n;(void)p;if(attached)assert(!(irq&DP_INTERRUPT_STATUS2_MASK));clocked=false;}
static int msm_dp_ctrl_usb4_dpin_set_rate(struct msm_dp_ctrl_private*c){(void)c;assert(clocked);return fault==3?-EIO:0;}
static int clk_prepare_enable(void*p){assert(clocked);if(p==(void*)2){if(fault==4)return -EIO;router_count++;}else{assert(router_count);if(fault==5)return -EIO;dpin_count++;}return 0;}
static void clk_disable_unprepare(void*p){assert(clocked);if(attached)assert(!(irq&DP_INTERRUPT_STATUS2_MASK));if(p==(void*)2){assert(router_count);router_count--;}else{assert(dpin_count);dpin_count--;}}
static void msm_dp_aux_usb4_unconfigure_link(void*p){(void)p;assert(clocked);}
static void msm_dp_ctrl_usb4_reset(struct msm_dp_ctrl_private*c,bool b){(void)c;(void)b;assert(clocked);}
static void msm_dp_ctrl_usb4_mainlink_restore(struct msm_dp_ctrl_private*c){(void)c;assert(clocked);if(attached){assert(!(irq&DP_INTERRUPT_STATUS2_MASK));irq|=9;}}
static void msm_dp_ctrl_usb4_tu_bank2_restore(struct msm_dp_ctrl_private*c){(void)c;assert(clocked);}
static void msm_dp_ctrl_usb4_post_train_restore(struct msm_dp_ctrl_private*c){(void)c;assert(clocked);}
'''
main=r'''
static u32 bits(unsigned v){return ((v&1)?1:0)|((v&2)?8:0)|((v&4)?64:0)|((v&8)?512:0);}
int main(void){
 int cases=0;
 for(unsigned status=0;status<16;status++)for(unsigned mask=0;mask<16;mask++)for(int on=0;on<2;on++){
  struct msm_dp_ctrl_private c={.core_clks_on=true};clocked=on;irq=bits(status)|(bits(mask)<<2);
  assert(msm_dp_ctrl_get_interrupt(&c)==bits(status));assert((irq&DP_INTERRUPT_STATUS2_MASK)==(bits(mask)<<2));assert((irq&DP_INTERRUPT_STATUS2)==(on?0:bits(status)));assert(!c.link_irq_lock);cases++;
 }
 /* Both ISR orderings: neither a queued handler nor a late handler rearms it. */
 for(int first=0;first<2;first++)for(unsigned status=0;status<16;status++){
  struct msm_dp_ctrl_private c={.core_clks_on=true};clocked=true;irq=DP_INTERRUPT_STATUS2_MASK|bits(status);
  if(first)msm_dp_ctrl_get_interrupt(&c);
  msm_dp_ctrl_link_irq_mask(&c,0,false);clocked=false;irq|=bits(status);
  msm_dp_ctrl_get_interrupt(&c);assert(!(irq&DP_INTERRUPT_STATUS2_MASK));
  clocked=true;msm_dp_ctrl_link_irq_mask(&c,DP_INTERRUPT_STATUS2_MASK,true);assert(irq==DP_INTERRUPT_STATUS2_MASK);cases++;
 }
 for(int usb=0;usb<2;usb++)for(int fail=0;fail<8;fail++)for(int bit=0;bit<2;bit++){
  struct msm_dp_ctrl_private c={.dpin_clk=(void*)1,.usb4_link_clk=(void*)2};attached=usb;fault=fail;clocked=false;router_count=dpin_count=0;irq=DP_INTERRUPT_STATUS2_MASK;selector=0xa4|bit;u32 original=selector;
  if(fail==6)c.dpin_clk=NULL;if(fail==7)c.usb4_link_clk=NULL;
  int ret=msm_dp_ctrl_link_clk_enable(&c.msm_dp_ctrl);
  bool failed=fail==1||fail==2||(usb&&fail>=3);
  if(failed){assert(ret<0&&!clocked&&!c.link_clks_on&&!router_count&&!dpin_count);assert(selector==original);if(usb&&fail!=1)assert(!(irq&DP_INTERRUPT_STATUS2_MASK));}
  else{
   assert(!ret&&clocked&&c.link_clks_on&&irq==DP_INTERRUPT_STATUS2_MASK);
   msm_dp_ctrl_link_clk_disable(&c.msm_dp_ctrl);assert(!clocked&&!c.link_clks_on&&!router_count&&!dpin_count&&selector==original);
   if(usb){assert(!(irq&DP_INTERRUPT_STATUS2_MASK));msm_dp_ctrl_get_interrupt(&c);assert(!(irq&DP_INTERRUPT_STATUS2_MASK));}
   /* Restart once as USB4 and once as native after provider detach. */
   attached=bit;fault=0;c.dpin_clk=(void*)1;c.usb4_link_clk=(void*)2;
   assert(!msm_dp_ctrl_link_clk_enable(&c.msm_dp_ctrl));assert(irq==DP_INTERRUPT_STATUS2_MASK);
   msm_dp_ctrl_link_clk_disable(&c.msm_dp_ctrl);assert(!clocked&&!router_count&&!dpin_count);
  }cases++;
 }
 printf("PASS %d IRQ/clock lifecycle cases\n",cases);
}
'''
variants={'correct':functions,'isr_rearms_mask':functions.replace('intr_ack | mask','intr_ack | DP_INTERRUPT_STATUS2_MASK'),'no_restart_drain':functions.replace('DP_INTERRUPT_STATUS2_MASK, true','DP_INTERRUPT_STATUS2_MASK, false')}
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);results={}
 for name,body in variants.items():
  f=p/(name+'.c');exe=p/name;f.write_text(header+body+main)
  flags=['-Wall','-Wextra','-Werror','-Wno-misleading-indentation'] if name=='correct' else ['-w']
  subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11',*flags,'-fsanitize=address,undefined',str(f),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True)
  if name=='correct':assert r.returncode==0,r.stderr;print(r.stdout.strip());results[name]='pass'
  else:assert body!=functions and r.returncode==134,name;results[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'cases':576,'ASan_UBSan':'pass','variants':results},indent=2)+'\n')
 print(results)
