#!/usr/bin/env python3
"""Exercise the extracted split function across topology shrink/grow transitions.

The rectangle stubs deliberately cover unrotated, unscaled RGB planes only.
This verifies stale-state removal, not the full DRM geometry implementation.
"""
import argparse,json,pathlib,subprocess,tempfile
HARNESS_HEADER=str(pathlib.Path(__file__).resolve().with_name('harness.h'))

def extract(text):
    start=text.index('static int dpu_plane_split(')
    end=text.index('\nstatic int dpu_plane_is_multirect_capable',start)
    return text[start:end]

PRE=r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint64_t u64; typedef uint32_t u32;
#define PIPES_PER_STAGE 2
#define DPU_DEBUG_PLANE(...) do {} while (0)
#define DRM_RECT_FMT ""
struct drm_rect { int x1,y1,x2,y2; };
struct dpu_sw_pipe_cfg { struct drm_rect src_rect,dst_rect; unsigned rotation; };
struct drm_framebuffer { unsigned width,height; };
struct drm_plane_state { struct drm_rect src,dst; struct drm_framebuffer *fb; unsigned rotation; };
struct dpu_plane_state { struct drm_plane_state base; struct dpu_sw_pipe_cfg pipe_cfg[4]; };
struct drm_plane { int unused; };
struct caps { unsigned max_linewidth; };
struct catalog { struct caps *caps; };
struct dpu_plane { struct drm_plane base; struct catalog *catalog; };
struct dpu_kms { struct { u64 max_core_clk_rate; } perf; };
struct drm_display_mode { int hdisplay,vdisplay; };
struct drm_crtc_state { struct drm_display_mode adjusted_mode; unsigned num_lm; };
static struct dpu_kms kms={.perf={UINT64_MAX}};
static int dpu_use_virtual_planes;
#define to_dpu_plane(p) ((struct dpu_plane *)(p))
#define to_dpu_plane_state(p) ((struct dpu_plane_state *)(p))
static struct dpu_kms *_dpu_plane_get_kms(struct drm_plane *p) { (void)p; return &kms; }
static unsigned dpu_crtc_get_num_lm(const struct drm_crtc_state *s) { return s->num_lm; }
static int drm_rect_width(const struct drm_rect *r) { return r->x2-r->x1; }
static int drm_rect_height(const struct drm_rect *r) { return r->y2-r->y1; }
static void drm_rect_fp_to_int(struct drm_rect *d,const struct drm_rect *s) {
 *d=(struct drm_rect){s->x1>>16,s->y1>>16,s->x2>>16,s->y2>>16};
}
static void drm_rect_rotate(struct drm_rect *r,unsigned w,unsigned h,unsigned rot) {
 (void)r;(void)w;(void)h;assert(rot==1);
}
#define drm_rect_rotate_inv drm_rect_rotate
static int drm_rect_clip_scaled(struct drm_rect *s,struct drm_rect *d,const struct drm_rect *c) {
 assert(drm_rect_width(s)==drm_rect_width(d)); assert(drm_rect_height(s)==drm_rect_height(d));
 int x1=d->x1>c->x1?d->x1:c->x1, y1=d->y1>c->y1?d->y1:c->y1;
 int x2=d->x2<c->x2?d->x2:c->x2, y2=d->y2<c->y2?d->y2:c->y2;
 if (x2<=x1 || y2<=y1) return 0;
 s->x1+=x1-d->x1;s->y1+=y1-d->y1;s->x2-=d->x2-x2;s->y2-=d->y2-y2;
 *d=(struct drm_rect){x1,y1,x2,y2};return 1;
}
static u64 _dpu_plane_calc_clk(const struct drm_display_mode *m,const struct dpu_sw_pipe_cfg *p) {
 (void)m;(void)p;return 0;
}
'''
POST=r'''
static void geometry(struct dpu_plane_state *s,struct drm_framebuffer *fb,int w,int h) {
 fb->width=w;fb->height=h;
 s->base=(struct drm_plane_state){.src={0,0,w<<16,h<<16},.dst={0,0,w,h},.fb=fb,.rotation=1};
}
int main(void) {
 unsigned cases=0;struct caps caps={4096};struct catalog catalog={&caps};
 struct dpu_plane plane={.catalog=&catalog};struct dpu_plane_state state;struct drm_framebuffer fb;
 const int widths[]={640,1920,2304,3840,6144},heights[]={480,1200,1536,2560},mixers[]={1,2,4};
 for (unsigned v=0;v<2;v++) for(unsigned mw=2048;mw<=4096;mw+=2048)
 for(unsigned wi=0;wi<5;wi++) for(unsigned hi=0;hi<4;hi++) for(unsigned mi=0;mi<3;mi++) {
  /* Populate an actual wide topology first; the candidate must discard it. */
  memset(&state,0,sizeof(state));dpu_use_virtual_planes=1;caps.max_linewidth=4096;
  geometry(&state,&fb,6144,2560);
  struct drm_crtc_state crtc={.adjusted_mode={6144,2560},.num_lm=4};
  assert(dpu_plane_split(&plane.base,&state.base,&crtc)==0);
  assert(drm_rect_width(&state.pipe_cfg[2].src_rect)==3072);
  dpu_use_virtual_planes=v;caps.max_linewidth=mw;
  geometry(&state,&fb,widths[wi],heights[hi]);
  crtc=(struct drm_crtc_state){.adjusted_mode={widths[wi],heights[hi]},.num_lm=mixers[mi]};
  unsigned stages=v?(mixers[mi]+1)/2:1;
  int ret=dpu_plane_split(&plane.base,&state.base,&crtc);
  if (widths[wi]/(int)stages>(int)(mw*2)) { assert(ret==-E2BIG);cases++;continue; }
  assert(ret==0);
  unsigned area=0;
  for(unsigned i=0;i<4;i++) {
   struct dpu_sw_pipe_cfg *cfg=&state.pipe_cfg[i];
   if (i>=stages*2 || !drm_rect_width(&cfg->src_rect)) {
    const struct dpu_sw_pipe_cfg zero={0};assert(!memcmp(cfg,&zero,sizeof(zero)));continue;
   }
   assert(cfg->src_rect.x1>=0 && cfg->src_rect.y1>=0);
   assert(cfg->src_rect.x2<=(int)fb.width && cfg->src_rect.y2<=(int)fb.height);
   assert(drm_rect_width(&cfg->src_rect)<=(int)mw);
   area+=drm_rect_width(&cfg->src_rect)*drm_rect_height(&cfg->src_rect);
  }
  assert(area==(unsigned)(widths[wi]*heights[hi]));cases++;
 }
 printf("%u\n",cases);return 0;
}
'''
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source',type=pathlib.Path);ap.add_argument('--cc',default='cc');args=ap.parse_args()
    body=extract(args.source.read_text());reset='memset(pstate->pipe_cfg, 0, sizeof(pstate->pipe_cfg));'
    assert body.count(reset)==1
    with tempfile.TemporaryDirectory() as tmp:
        tmp=pathlib.Path(tmp);results={}
        for label,text in [('candidate',body),('retained_old_rectangles',body.replace(reset,'')),('only_clear_first_pair',body.replace('sizeof(pstate->pipe_cfg)','2 * sizeof(pstate->pipe_cfg[0])'))]:
            c=tmp/(label+'.c');exe=tmp/label;c.write_text(PRE+text+POST)
            build=subprocess.run([args.cc,'-include',HARNESS_HEADER,'-std=gnu11','-Wall','-Wextra','-Wno-sign-compare','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-o',str(exe),str(c)],capture_output=True,text=True)
            assert build.returncode==0,build.stderr
            r=subprocess.run([str(exe)],capture_output=True,text=True)
            if label=='candidate':assert r.returncode==0,r.stderr;results['extracted_cases']=int(r.stdout)
            else:assert r.returncode==134,'negative control unexpectedly passed';results[label]='rejected'
        print(json.dumps(dict(results,ASan_UBSan='pass',scope='Unrotated/unscaled plane state recomputation; hardware validation required'),indent=2))
if __name__=='__main__':main()
