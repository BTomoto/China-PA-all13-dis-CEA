"""Generate the manuscript figures from this notebook's current results."""
from pathlib import Path
import io, re, gc, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.text import Text
from matplotlib.patches import Patch, Wedge, FancyBboxPatch, Circle, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter
from reporting import AGES, DISEASES, save as save_data

def build_figures(root):
    R=Path(root);folder=R/'outputs/figures';folder.mkdir(parents=True,exist_ok=True)
    def read(name):return pd.read_csv(R/'outputs'/name)
    # Refresh installed fonts that may be absent from Matplotlib's cache.
    for font_path in font_manager.findSystemFonts():
        if 'times' in Path(font_path).name.lower():
            font_manager.fontManager.addfont(font_path)
    try:
        font_manager.findfont('Times New Roman',fallback_to_default=False)
        font='Times New Roman'
    except ValueError:
        font='DejaVu Serif'
        print('Times New Roman is unavailable; using DejaVu Serif. Install Times New Roman for publication typography.')
    def reset(sans=False):
        plt.rcdefaults()
        plt.rcParams.update({'font.family':[font],'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'figure.facecolor':'white','pdf.fonttype':42,'ps.fonttype':42,'mathtext.fontset':'custom','mathtext.rm':font,'mathtext.it':font+':italic','mathtext.bf':font+':bold','mathtext.fallback':None})
    records={}
    def save(fig,name):
        texts=[t.get_text() for t in fig.findobj(Text) if t.get_text()]
        assert not any(re.search(r'[\u3400-\u9fff]',s) for s in texts),name
        for ext in ['png','pdf']:
            buf=io.BytesIO();fig.savefig(buf,format=ext,dpi=600,facecolor='white')
            (folder/f'{name}.{ext}').write_bytes(buf.getvalue())
        records[name]={'dpi':600,'font':font,'text_elements':texts}
        plt.close(fig);gc.collect();print('Exported',name,flush=True)
    export=save
    s29=read('tables/S29.csv');s29['condition']=np.where(s29.outcome_id.str.endswith('_cancer'),'cancer',s29.outcome_id)
    save_data(R,'figure_data/Main_Figure2_groups.csv',s29.groupby('condition',as_index=False)[['avoided_value','discounted_savings_main_2025_cny']].sum())
    save_data(R,'figure_data/Main_Figure2_cancer.csv',s29.loc[s29.outcome_id.str.endswith('_cancer'),['outcome_id','avoided_value','discounted_savings_main_2025_cny']])
    health=read('disease_age_sex_health.csv');qty=read('disease_age_sex_quantity.csv');medical=read('age_sex_disease_medical_10y.csv')
    dfs=[medical,health[health.horizon_years.eq(10)&health.measure_short.eq('DALY')],qty[qty.horizon_years.eq(10)]]
    for i,(d,c) in enumerate(zip(dfs,['medical_savings_2025_cny','discounted_value','avoided_value']),1):
        p=d.pivot_table(index='age_group',columns='outcome_id',values=c,aggfunc='sum').reindex(AGES).fillna(0)
        save_data(R,f'figure_data/Main_Figure3_panel{i}.csv',p.reset_index())
    conv=read('figure_data/convergence.csv');rows=[]
    for metric,g in conv.groupby('metric'):
        g=g.sort_values('checkpoint_draws').copy();g['deviation_percent']=(g.cumulative_mean/g.cumulative_mean.iloc[-1]-1)*100;rows.append(g)
    save_data(R,'figure_data/convergence_deviation.csv',pd.concat(rows,ignore_index=True))
    def tidy(ax,grid=None):
        ax.set_axisbelow(True)
        if grid:ax.grid(axis=grid,color='#eaeaea',linewidth=.7)
    def label(ax,letter,x=-.25,y=1.06):ax.text(x,y,letter,transform=ax.transAxes,weight='bold',fontsize=17,va='bottom')

    # Match the actual RGB fills sampled from the source manuscript images.
    conditions=['hypertension','depression','stroke','dementia','type2_diabetes','coronary_heart_disease','cancer']
    colors=dict(zip(conditions,['#7bc4b1','#e5a53b','#6fa8c6','#a96f3f','#4e9c82','#2b6f92','#8c6fb1']))
    cancers=['gastric_cancer','colon_cancer','oesophageal_cancer','breast_cancer','renal_cancer','bladder_cancer','endometrial_cancer']
    # Data uses esophageal spelling in this package.
    cdata=read('figure_data/Main_Figure2_cancer.csv').set_index('outcome_id')
    cancers=[c if c in cdata.index else c.replace('oesophageal','esophageal') for c in cancers]
    colors.update(dict(zip(cancers,['#527c95','#b28365','#5e9689','#c2a059','#8a79a6','#79a9b7','#a0848e'])))
    names=dict(zip(conditions,['Hypertension','Depression','Stroke','Dementia','Type 2 diabetes','Ischaemic heart disease','Cancer']))
    names.update(dict(zip(cancers,['Stomach cancer','Colorectal cancer','Esophageal cancer','Breast cancer','Kidney cancer','Bladder cancer','Endometrial cancer'])))
    short=dict(zip(conditions,['HTN','Depression','Stroke','Dementia','T2D','IHD','Cancer']))
    short.update({c:n.replace(' cancer','') for c,n in names.items() if c in cancers})
    reset()
    fig=plt.figure(figsize=(14.6267,16.8133))
    gdata=read('figure_data/Main_Figure2_groups.csv').set_index('condition')
    def donut(rect,frame,order,metric,title,letter,positions):
        ax=fig.add_axes(rect);v=frame.loc[order,metric]
        # Every wedge has the SAME centre and inner radius. Only the outer
        # radius changes, reproducing the stepped outside edge of the source.
        radii=[1.00,1.04,1.13,1.19,1.25,1.31,1.37] if letter=='A' else [1.00,1.04,1.08,1.13,1.20,1.27,1.34]
        inner_radius=.46
        theta=90.0;ws=[]
        for k,radius in zip(order,radii):
            span=float(v[k]/v.sum()*360)
            wedge=Wedge((0,0),radius,theta-span,theta,width=radius-inner_radius,
                        facecolor=colors[k],edgecolor='white',linewidth=.6)
            ax.add_patch(wedge);ws.append(wedge);theta-=span
            assert abs((wedge.r-wedge.width)-inner_radius)<1e-12
            assert wedge.center==(0,0)
        assert abs(theta+270)<1e-9
        ax.set_aspect('equal');ax.set_axis_off()
        for w,k in zip(ws,order):
            angle=np.deg2rad((w.theta1+w.theta2)/2)
            x=w.center[0]+np.cos(angle)*(w.r+.025);y=w.center[1]+np.sin(angle)*(w.r+.025)
            tx,ty=positions[k];side=1 if tx>0 else -1
            ax.plot([x,tx-side*(.8 if ty>1 else .25),tx-side*.055],[y,ty,ty],color='#888888',lw=.65,clip_on=False)
            ax.text(tx,ty+.035,names[k],ha='left' if side>0 else 'right',va='bottom',fontsize=9.3)
            ax.text(tx,ty-.025,f'{v[k]/v.sum()*100:.2f}%',ha='left' if side>0 else 'right',va='top',fontsize=9.3,weight='bold')
        ax.set(xlim=(-2.08,2.1),ylim=(-1.55,1.7))
        fig.text(rect[0]+rect[2]/2,.984 if letter in 'AB' else .464,title,ha='center',fontsize=13)
        fig.text(.037 if letter in 'AE' else .474,.973 if letter in 'AB' else .451,letter,weight='bold',fontsize=17)
        return ax
    posA=dict(zip(conditions,[(1.47,-.35),(-1.42,-.54),(-1.42,1.01),(-1.42,1.38),(-1.42,1.76),(1.08,1.86),(1.08,1.49)]))
    ordB=['dementia','type2_diabetes','depression','hypertension','stroke','cancer','coronary_heart_disease']
    posB=dict(zip(ordB,[(1.48,.57),(.61,-1.31),(-1.45,-.45),(-1.45,.29),(-1.45,.74),(-1.45,1.38),(.80,1.68)]))
    posE=dict(zip(cancers,[(1.47,.32),(1.47,-1.33),(-1.42,-.38),(-1.42,.81),(-1.42,1.19),(-1.42,1.55),(1.16,1.73)]))
    posF=dict(zip(cancers,[(1.47,.32),(1.47,-1.33),(-1.42,.02),(-1.42,.96),(-1.42,1.33),(-1.42,1.68),(1.14,1.57)]))
    donut([.105,.740,.286,.208],gdata,conditions,'avoided_value','Avoided Disease Burden by Condition','A',posA)
    donut([.542,.740,.286,.208],gdata,ordB,'discounted_savings_main_2025_cny','Direct Medical Cost Savings by Condition','B',posB)
    donut([.105,.223,.286,.208],cdata,cancers,'avoided_value','Preventable Incident Cancer Cases by Subtype','E',posE)
    donut([.542,.223,.286,.208],cdata,cancers,'discounted_savings_main_2025_cny','Direct Medical Cost Savings by Cancer Subtype','F',posF)
    for order,y in [(conditions,.855),(cancers,.34)]:
        fig.legend([Patch(color=colors[k]) for k in order],[names[k] for k in order],loc='upper left',bbox_to_anchor=(.89,y),frameon=False,fontsize=8,handlelength=1.2,handleheight=1.3,labelspacing=1.05)
    def bars(rect,frame,order,metric,scale,ylabel,xlabel,letter,fmt):
        ax=fig.add_axes(rect);v=frame.loc[order,metric]/scale
        ax.bar(range(len(order)),v,color=[colors[k] for k in order],width=.49)
        ax.set_xticks(range(len(order)),[short[k] for k in order]);ax.set_ylabel(ylabel,fontsize=9,labelpad=15);ax.set_xlabel(xlabel,fontsize=10)
        ax.set_ylim(0,max(v)*1.12);ax.tick_params(axis='both',labelsize=8,length=2,color='#777777');ax.tick_params(axis='x',length=0)
        for sp in ['left','bottom']:ax.spines[sp].set_color('#777777');ax.spines[sp].set_linewidth(.7)
        for i,n in enumerate(v):ax.text(i,n+max(v)*.035,fmt(n),ha='center',va='bottom',fontsize=8.5,color='#333333')
        label(ax,letter,-.27,1.05)
    bars([.111,.566,.273,.151],gdata,conditions,'avoided_value',1e4,'Avoided disease burden\n\n(10,000 category-specific units)','Disease','C',lambda x:f'{x:.1f}')
    bars([.548,.566,.273,.151],gdata,ordB,'discounted_savings_main_2025_cny',1e8,'Direct medical cost savings\n\n(CNY 100 million)','Disease','D',lambda x:f'{x:.3g}')
    bars([.111,.045,.273,.151],cdata,cancers,'avoided_value',1,'Preventable incident cancer cases\n\n(10-year total)','Cancer type','G',lambda x:f'{x:,.0f}')
    bars([.548,.045,.273,.151],cdata,cancers,'discounted_savings_main_2025_cny',1e8,'Direct medical cost savings\n\n(CNY 100 million, 10-year total)','Cancer type','H',lambda x:f'{x:.2f}')
    save(fig,'Main_Figure2')


    # Source Figure 3: shared age rows, three horizontal stacked panels, serif type.
    reset();fig,axes=plt.subplots(1,3,figsize=(12.312,6.78),sharey=True)
    fig.subplots_adjust(left=.058,right=.846,top=.925,bottom=.09,wspace=.24)
    cols3=['#2f6b9a','#74a9cf','#4e9f7d','#79c6b0','#e2a03a','#a46a3d','#8b9cc4','#ba6d88','#cc593c','#b880b7','#8171ac','#b58b6f','#8c8c8c']
    longnames=['Ischaemic heart disease','Stroke','Type 2 diabetes','Hypertension','Depression','Dementia','Bladder cancer','Breast cancer','Colorectal cancer','Endometrial cancer','Oesophageal cancer','Gastric cancer','Kidney cancer']
    for i,ax in enumerate(axes):
        df=read(f'figure_data/Main_Figure3_panel{i+1}.csv').set_index('age_group').reindex(AGES);left=np.zeros(len(AGES))
        for d,c,n in zip(DISEASES,cols3,longnames):
            v=(df[d].to_numpy() if d in df else np.zeros(len(df)))/([1e8,1e3,1e3][i]);ax.barh(np.arange(len(AGES)),v,left=left,color=c,height=.72,label=n,linewidth=0);left+=v
        ax.set_yticks(np.arange(len(AGES)),[x.replace('-','–') for x in AGES]);ax.tick_params(labelsize=7,length=0)
        ax.spines['left'].set_visible(False);ax.spines['bottom'].set_color('#777777');tidy(ax,'x');ax.margins(x=.04)
        ax.set_xlabel(['Direct medical cost savings\n(CNY 100 million)','DALYs averted\n(thousands)','Prevented disease events / patient-years\n(thousands)'][i],fontsize=8)
        label(ax,chr(65+i),-.12,1.04)
    axes[0].set_ylabel('Age group (years)',fontsize=8,labelpad=16)
    axes[-1].legend(title='Disease',title_fontsize=8,loc='center left',bbox_to_anchor=(1.08,.5),fontsize=7,frameon=False,handlelength=1.2,labelspacing=.3)
    save(fig,'Main_Figure3')

    # Original Figure 4's blue/purple bars, red cumulative curve, and structural-period shading.
    reset(True);traj=read('annual_cumulative_economic_trajectory.csv')
    fig,axes=plt.subplots(2,1,figsize=(12,9.3));fig.subplots_adjust(left=.1,right=.89,top=.94,bottom=.07,hspace=.36)
    for i,(ax,metric,c) in enumerate(zip(axes,['medical','gdp_equivalent'],['#6395b3','#917cb0'])):
        bars_=ax.bar(traj.year,traj[f'annual_{metric}_bn'],color=c,width=.7,zorder=3)
        ax.axvspan(2034.5,2050.6,color='#f1f4f9',zorder=0);ax.axvline(2034.5,color='#939baa',linestyle='--',linewidth=1)
        ax.set_xlim(2024.3,2050.8);ax.set_ylim(0,traj[f'annual_{metric}_bn'].max()*1.15);ax.set_ylabel('Annual (2025 CNY billion)');ax.set_xlabel('Year');tidy(ax,'y')
        ax.set_title(['A. Direct medical cost savings','B. GDP-equivalent productivity gains'][i],loc='left',weight='bold',fontsize=15,pad=16)
        twin=ax.twinx();line,=twin.plot(traj.year,traj[f'cumulative_{metric}_bn'],color='#d1495b',lw=2.4,marker='o',markevery=[0,5,10,15,20,25],ms=4)
        twin.spines['right'].set_visible(True);twin.set_ylabel('Cumulative (2025 CNY billion)');twin.set_ylim(bottom=0)
        ax.text(2042.5,.97,'Long-term structural extension',transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=10,color='#6b7280')
        ax.legend([bars_[0],line],['Annual (left axis)','Cumulative (right axis)'],loc='upper left',frameon=False,fontsize=10)
    save(fig,'Main_Figure4')

    reset();front=read('tables/S20.csv');fig,axes=plt.subplots(1,2,figsize=(11.855,5.27));fig.subplots_adjust(left=.083,right=.98,bottom=.14,top=.91,wspace=.20)
    for ax,h in zip(axes,[5,10]):
        g=front[front.horizon_years.eq(h)];f=g[g.frontier_status.eq('FRONTIER')].sort_values('mean_discounted_dalys')
        ax.scatter(g.mean_discounted_dalys/1e6,g.mean_cost_2025_cny/1e9,color='#888888',s=70,zorder=3)
        ax.plot(f.mean_discounted_dalys/1e6,f.mean_cost_2025_cny/1e9,'o-',color='#9e2a2b',lw=2,ms=8,zorder=4)
        for r in g.itertuples():ax.annotate(r.scenario_id,(r.mean_discounted_dalys/1e6,r.mean_cost_2025_cny/1e9),xytext=(5,4),textcoords='offset points',fontsize=12)
        ax.set(title=f'{h}-year main horizon',xlabel='Mean discounted DALYs averted (millions)',ylabel='Mean programme cost (¥ billion)');tidy(ax,'both');ax.margins(.06)
    save(fig,'Supp_FigureS2')

    # Figure S4, matching the original two-by-two layout and the original scenario colours.
    reset();plt.rcParams['font.size']=12
    pair=read('figure_data/S0_S6_CEAC.csv');restricted=read('figure_data/restricted_S1_S5_CEAC.csv')
    fig,axes=plt.subplots(2,2,figsize=(13.2,9.1),sharey=True);fig.subplots_adjust(left=.065,right=.98,top=.934,bottom=.142,hspace=.44,wspace=.14)
    pal=dict(zip(['S1','S2','S3','S4','S5'],['#dfa345','#76a7c6','#a97752','#46977a','#9b83ad']))
    for i,h in enumerate([5,10]):
        d=pair[pair.horizon_years==h];ax=axes[i,0]
        for sid,c,lab in [('S6','#306f9d','S6 Combined policy package'),('S0','#999999','S0 Baseline trend')]:ax.plot(d.wtp/1000,d[sid+'_probability'],color=c,lw=1.7,label=lab)
        ax.legend(loc='center right',frameon=False,fontsize=11)
        for w in [50000,100000,150000]:
            y=d.loc[d.wtp.eq(w),'S6_probability'].iloc[0];ax.plot(w/1000,y,'o',mfc='white',mec='#306f9d',ms=4.5,clip_on=False)
            ax.annotate(f'{y*100:.2f}%',(w/1000,y),xytext=(-5,-24),textcoords='offset points',ha='right' if w==150000 else 'center',color='#306f9d',fontsize=11)
        for sid,c in pal.items():
            d=restricted[(restricted.horizon_years==h)&(restricted.scenario_id==sid)];axes[i,1].plot(d.wtp/1000,d.probability,color=c,lw=1.7,label=sid)
        d=restricted[restricted.horizon_years==h].drop_duplicates('wtp').sort_values('wtp')
        axes[i,1].plot(d.wtp/1000,d.ceaf_probability,'--',color='#35574b',lw=1,label='CEAF')
        for w in [50000,100000,150000]:
            y=d.loc[d.wtp.eq(w),'ceaf_probability'].iloc[0];axes[i,1].plot(w/1000,y,'D',mfc='white',mec='#35574b',ms=5.5,clip_on=False)
            axes[i,1].annotate(f'{y*100:.2f}%',(w/1000,y),xytext=(-5,-25),textcoords='offset points',ha='right' if w==150000 else 'center',color='#46977a',fontsize=11)
        for j,ax in enumerate(axes[i]):
            ax.set(xlim=(0,150),ylim=(0,1.045),xticks=np.arange(0,151,25),yticks=np.arange(0,1.01,.2),xlabel='Willingness-to-pay threshold (CNY thousands/DALY)')
            ax.set_title(f'{chr(65+i*2+j)} '+('S6 vs. S0: ' if j==0 else 'S1–S5 comparison: ')+f'{h}-year horizon (2025–{2024+h})',loc='left',fontsize=12,pad=18)
            ax.tick_params(labelsize=11,length=3,width=.6);tidy(ax,'y')
            for w in [50,100,150]:ax.axvline(w,color='#dddddd',lw=.7,ls=(0,(3,5)),zorder=0)
        axes[i,0].set_ylabel('Probability of cost-effectiveness',labelpad=12)
    labs=['S1 Health communication','S2 Community activity and organisational support','S3 Public fitness facilities','S4 Integrated sport and health services','S5 Digital fitness services','CEAF']
    handles=[Line2D([0],[0],color=c,lw=1.7) for c in pal.values()]+[Line2D([0],[0],color='#35574b',ls='--',lw=1,marker='D',mfc='white',ms=5)]
    fig.legend(handles,labs,loc='lower center',bbox_to_anchor=(.54,.024),ncol=3,frameon=False,fontsize=10.5,columnspacing=1.8,labelspacing=.7)
    save(fig,'Supp_FigureS4')

    reset(True);m=read('tables/S24.csv');m=m[m.horizon_years.eq(10)].sort_values('discounted_savings_main_2025_cny',ascending=False)
    fig,axes=plt.subplots(1,2,figsize=(14.92,7.144));fig.subplots_adjust(left=.13,right=.97,bottom=.12,top=.82,wspace=.40)
    for i,ax in enumerate(axes):
        ax.spines['left'].set_color('#94a0aa');ax.spines['bottom'].set_color('#94a0aa');ax.tick_params(length=0,labelsize=10,colors='#303b47')
        ax.text(-.02,1.13,chr(65+i),transform=ax.transAxes,color='#244b74',weight='bold',fontsize=17)
        ax.text(.06,1.13,['Direct medical savings by disease','Cumulative economic outcomes'][i],transform=ax.transAxes,weight='bold',fontsize=13,color='#222c36')
    labelsmap=dict(zip(DISEASES,longnames))
    v=m.discounted_savings_main_2025_cny/1e9;ax=axes[0]
    ax.barh(np.arange(len(m)),v,color=['#d39b36' if x.endswith('_cancer') else '#237f87' for x in m.outcome_id],height=.61)
    ax.set_yticks(np.arange(len(m)),[labelsmap[x] for x in m.outcome_id]);ax.invert_yaxis();ax.set_xlim(0,v.max()*1.13);tidy(ax,'x')
    for i,x in enumerate(v):ax.text(x+v.max()*.014,i,f'{x:.1f}' if x>=1 else f'{x:.2f}',va='center',fontsize=9,color='#303b47')
    ax.set_xlabel('Direct medical savings (2025 CNY billion)');ax.text(.06,1.045,f'2025–2034; total = {v.sum():.3f} billion',transform=ax.transAxes,color='#78828f',fontsize=10)
    ax.text(.03,-.13,'Teal: non-cancer conditions     Gold: cancers',transform=ax.transAxes,color='#78828f',fontsize=10)
    ax=axes[1];ax.axvspan(2025,2029.5,color='#edf5f0');ax.axvspan(2029.5,2034.5,color='#f1f5fa')
    for metric,c,lab in [('gdp_equivalent','#527dad','GDP-equivalent productivity benefit'),('medical','#73a98b','Direct medical savings')]:
        y=traj[f'cumulative_{metric}_bn'];ax.plot(traj.year,y,color=c,lw=3,label=lab)
        for yr in [2029,2034,2050]:
            value=y[traj.year.eq(yr)].iloc[0];ax.plot(yr,value,'o',color=c,ms=6);ax.annotate(f'{value:.3f}',(yr,value),xytext=(0,10),textcoords='offset points',ha='center',color=c,fontsize=9,bbox={'facecolor':'white','edgecolor':'none','pad':.6})
    ax.set(xlim=(2025,2050),ylim=(0,traj.cumulative_gdp_equivalent_bn.max()*1.12),xticks=[2025,2029,2034,2040,2050],ylabel='Cumulative value (2025 CNY billion)');tidy(ax,'y')
    ax.text(.06,1.045,'26-year structural scenario, 2025–2050',transform=ax.transAxes,color='#78828f',fontsize=10);ax.legend(loc='upper left',frameon=False,fontsize=10)
    save(fig,'Supp_FigureS5')

    reset();conv=read('figure_data/convergence_deviation.csv');fig,ax=plt.subplots(figsize=(10.675,5.535));fig.subplots_adjust(left=.083,right=.985,bottom=.135,top=.97)
    keys=conv.metric.unique();print('convergence metrics',keys)
    for match,c,lab in [('dalys','#2a6f97','Discounted DALYs'),('programme','#9e2a2b','Programme cost'),('net','#6a994e','D4-only partial payer net cost')]:
        key=next(k for k in keys if match in k);d=conv[conv.metric.eq(key)].sort_values('checkpoint_draws');ax.plot(d.checkpoint_draws,d.deviation_percent,'o-',color=c,lw=2,ms=8,label=lab)
    ax.set(xscale='log',xlabel='Cumulative draws (log scale)',ylabel='Deviation from 10,000-draw mean (%)');tidy(ax,'both');ax.axhline(0,color='#555555',lw=1);ax.legend(loc='upper right',frameon=False,fontsize=12)
    save(fig,'Supp_FigureS6')

    reset()
    d=pd.read_csv(R/'outputs/figure_data/reference_S0_S6_CEAC.csv')
    table=pd.read_csv(R/'outputs/tables/S22.csv')
    assert not d.duplicated(['horizon_years','wtp','scenario_id']).any()
    assert np.allclose(d.groupby(['horizon_years','wtp']).probability.sum(),1)
    for r in table.itertuples():
        actual=d[(d.horizon_years==r.horizon_years)&(d.wtp==r.wtp_cny_per_daly)&(d.scenario_id==r.scenario_id)].probability.item()
        assert abs(actual-r.probability_cost_effective)<1e-12

    # Use exactly the palette, typography and line/grid settings of revised Figure S4.
    palette={'S0':'#999999','S1':'#dfa345','S2':'#76a7c6','S3':'#a97752','S4':'#46977a','S5':'#9b83ad','S6':'#306f9d'}
    labels={'S0':'S0 Baseline trend','S1':'S1 Health communication','S2':'S2 Community activity and organisational support','S3':'S3 Public fitness facilities','S4':'S4 Integrated sport and health services','S5':'S5 Digital fitness services','S6':'S6 Combined policy package'}
    fig,axes=plt.subplots(1,2,figsize=(13.2,5.35),sharey=True)
    fig.subplots_adjust(left=.065,right=.98,top=.873,bottom=.316,wspace=.14)
    for i,(ax,h) in enumerate(zip(axes,[5,10])):
        dh=d[d.horizon_years==h]
        for sid,c in palette.items():
            g=dh[dh.scenario_id==sid].sort_values('wtp')
            ax.plot(g.wtp/1000,g.probability,color=c,lw=1.7,label=labels[sid])
        # Highlight both principal competing curves using the hollow markers of S4.
        for sid in ['S4','S6']:
            for w in [50000,100000,150000]:
                y=dh[(dh.scenario_id==sid)&(dh.wtp==w)].probability.item()
                c=palette[sid]
                ax.plot(w/1000,y,'o',mfc='white',mec=c,ms=4.5,clip_on=False)
                dy=-23 if (h==5 and sid=='S4') or (h==10 and sid=='S6') else 11
                ax.annotate(f'{y*100:.2f}%',(w/1000,y),xytext=(-5,dy),textcoords='offset points',ha='right' if w==150000 else 'center',color=c,fontsize=11)
        ax.set(xlim=(0,150),ylim=(0,1.045),xticks=np.arange(0,151,25),yticks=np.arange(0,1.01,.2),xlabel='Willingness-to-pay threshold (CNY thousands/DALY)')
        ax.set_title(f'{chr(65+i)} S0–S6 comparison: {h}-year horizon (2025–{2024+h})',loc='left',fontsize=12,pad=18)
        ax.tick_params(labelsize=11,length=3,width=.6)
        ax.set_axisbelow(True);ax.grid(axis='y',color='#eaeaea',linewidth=.7)
        for w in [50,100,150]:ax.axvline(w,color='#dddddd',lw=.7,ls=(0,(3,5)),zorder=0)
    axes[0].set_ylabel('Probability of cost-effectiveness',labelpad=12)
    handles=[Line2D([0],[0],color=c,lw=1.7) for c in palette.values()]
    fig.legend(handles,[labels[s] for s in palette],loc='lower center',bbox_to_anchor=(.53,.006),ncol=3,frameon=False,fontsize=10.5,columnspacing=1.8,labelspacing=.7)

    save(fig,'Supp_FigureS3')
    # Figure 1: exact formal 2025 baseline with the original blue/red stacked-bar layout.
    reset();baseline=read('model_baseline_age_sex.csv')
    fig,axes=plt.subplots(1,2,figsize=(12,5.37),sharey=True)
    fig.subplots_adjust(left=.075,right=.99,top=.79,bottom=.20,wspace=.09)
    for i,(ax,sex) in enumerate(zip(axes,['Female','Male'])):
        d=baseline[baseline.sex==sex].set_index('age_group').reindex(AGES)
        assert np.allclose(d.p_inactive+d.p_active,1)
        ax.bar(np.arange(len(AGES)),d.p_inactive,color='#b35c56',width=.70)
        ax.bar(np.arange(len(AGES)),d.p_active,bottom=d.p_inactive,color='#4c78a8',width=.70)
        ax.set_xticks(np.arange(len(AGES)),AGES,rotation=45,ha='right');ax.set_ylim(0,1)
        ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_yticks(np.arange(0,1.01,.2))
        ax.set_title(sex,weight='bold',fontsize=13,pad=8);ax.grid(axis='y',color='#e5e5e5',lw=.6);ax.set_axisbelow(True)
        ax.text(-.09,1.045,chr(65+i),transform=ax.transAxes,fontsize=15,weight='bold')
        for sp in ['left','bottom']:ax.spines[sp].set_color('#888888')
    axes[0].set_ylabel('Proportion')
    fig.legend([Patch(color='#b35c56'),Patch(color='#4c78a8')],['Insufficient (<600 MET-min/week)','Meets recommendation (≥600 MET-min/week)'],loc='upper center',bbox_to_anchor=(.54,.98),ncol=2,frameon=False,fontsize=11)
    export(fig,'Main_Figure1')

    # Figure S1: translate the complete original process diagram as editable vector objects.
    reset();fig=plt.figure(figsize=(18,12));ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,18);ax.set_ylim(0,12);ax.axis('off')
    blue='#225c92';teal='#00968f';ink='#17212e';muted='#7e8b9b'
    def box(x,y,w,h,title,num,color,header=.78):
        ax.add_patch(FancyBboxPatch((x+.04,y-.06),w,h,boxstyle='round,pad=.02,rounding_size=.15',fc='#edf2f5',ec='none',zorder=0))
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.02,rounding_size=.15',fc='#fcfdfe',ec=color,lw=1.0))
        ax.add_patch(Rectangle((x+.02,y+h-header),w-.04,header-.1,fc='#d7e5f1' if color==blue else '#d8efec',ec='none'))
        ax.add_patch(Circle((x+.40,y+h-header/2-.015),.265,fc=color,ec='none',zorder=4))
        ax.text(x+.40,y+h-header/2-.015,num,ha='center',va='center',fontsize=17 if len(num)==1 else 14,weight='bold',color='white',zorder=5)
        ax.text(x+.79,y+h-header/2-.015,title,ha='left',va='center',fontsize=12.4,weight='bold',color=color,linespacing=1.15)
    def item(x,y,w,text,size=13):ax.text(x+w/2,y,text,ha='center',va='center',fontsize=size,color=ink,linespacing=1.42)
    def rule(x,y,w,color='#b2cadb'):ax.plot([x+.18,x+w-.18],[y,y],lw=.7,color=color)
    def arrow(p,q,color=blue,lw=1.6,style='-'):
        ax.add_patch(FancyArrowPatch(p,q,arrowstyle='-|>',mutation_scale=15,linewidth=lw,color=color,linestyle=style,shrinkA=0,shrinkB=0))
    xs=[.30,3.65,6.95,10.02];ws=[3.12,3.04,2.80,2.73];y=3.52;h=7.35
    for x,w,title,num,c in zip(xs,ws,['Policy context\nand scenarios','Population and\nbaseline inputs','Physical activity\nexposure','Health effects'],['1','2','3','4'],[blue,teal,blue,teal]):box(x,y,w,h,title,num,c)
    x=xs[0];w=ws[0]
    item(x,9.68,w,'Combined policy package\n(five implementation pathways)',12.4)
    item(x,8.43,w,'Health communication\nCommunity activity support\nPublic fitness facilities\nIntegrated sport and health services\nDigital fitness services',11.6)
    ax.plot([x+.18,x+w-.18],[7.12,7.12],color='#7ba7cd',ls=(0,(4,3)),lw=.9)
    for yy,title,body in [(5.47,'Baseline trend scenario','Continuation of existing\nphysical activity trends'),(3.72,'Combined policy scenario','Implementation of the national\nphysical activity policy package')]:
        ax.add_patch(FancyBboxPatch((x+.18,yy),w-.36,1.47,boxstyle='round,pad=.025,rounding_size=.12',fc='#e8f2f8',ec='#88b5d9',lw=.7))
        item(x,yy+1.10,w,title,12.1);item(x,yy+.54,w,body,11.8)
    x=xs[1];w=ws[1]
    for yy,text in [(9.31,'Adults aged ≥20 years\nin mainland China'),(7.94,'Stratification by age and sex'),(6.96,'Baseline physical activity'),(5.83,'Baseline burden of\n13 health outcomes'),(4.53,'Relative risk evidence')]:item(x,yy,w,text,12.6)
    for yy in [8.65,7.47,6.43,5.12]:rule(x,yy,w)
    x=xs[2];w=ws[2]
    for yy,text in [(9.31,'Insufficient physical activity:\n<600 MET-min/week'),(7.99,'Sufficient physical activity:\n≥600 MET-min/week'),(6.47,'Policy-induced reduction in\nphysical inactivity'),(4.81,'Comparison with the\nbaseline trend scenario')]:item(x,yy,w,text,12.0)
    for yy in [8.65,7.30,5.66]:rule(x,yy,w)
    x=xs[3];w=ws[3]
    for yy,text in [(9.37,'Potential impact fraction\n(PIF) model'),(8.06,'Estimation by age, sex,\nyear and health outcome'),(6.88,'Incident cases averted'),(5.94,'Deaths averted'),(5.05,'YLDs and YLLs reduced'),(4.20,'DALYs averted')]:item(x,yy,w,text,12.0)
    for yy in [8.78,7.34,6.41,5.52,4.62]:rule(x,yy,w)
    for i in range(3):arrow((xs[i]+ws[i]+.03,7.35),(xs[i+1]-.025,7.35))
    x=13.36;w=4.33
    box(x,7.33,w,4.50,'Primary cost-effectiveness\nanalysis','5a',blue)
    for yy,text in [(10.71,'Programme implementation costs'),(10.00,'Incremental cost-effectiveness ratio (ICER)'),(9.18,'Main evaluation horizons:\n2025–2029 and 2025–2034'),(8.36,'3% annual discount rate'),(7.67,'Medical cost savings do not offset\nprogramme costs in the primary ICER')]:item(x,yy,w,text,12.0)
    for yy in [10.36,9.65,8.74,8.02]:rule(x,yy,w)
    box(x,2.85,w,4.18,'Extended economic\nevaluation','5b',blue)
    for yy,text in [(5.96,'Direct medical cost savings'),(5.41,'Public payer net costs'),(4.86,'Societal net benefit and benefit–cost ratio'),(4.13,'GDP-equivalent productivity gains\n• Physical activity-related productivity\n• Labour supply preserved by averting deaths'),(3.19,'Long-term structural scenario to 2050')]:item(x,yy,w,text,11.9)
    for yy in [5.69,5.13,4.57,3.56]:rule(x,yy,w)
    arrow((12.78,8.06),(13.10,9.48));arrow((13.10,9.48),(13.34,9.48))
    arrow((12.78,7.00),(13.10,5.37));arrow((13.10,5.37),(13.34,5.37))
    # Shared uncertainty panel and dashed links back to all model components.
    box(2.35,.42,13.27,1.72,'Uncertainty analysis','6','#627080',header=.68)
    item(2.50,.96,6.25,'Joint health and programme-cost PSA\n(10,000 draws)',12.5)
    item(9.00,.96,6.45,'Independent probabilistic sensitivity analysis\nof economic parameters (10,000 draws)',12.5)
    ax.plot([8.92,8.92],[.66,1.31],color='#a1aab5',lw=.7)
    ax.plot([1.86,16.30],[2.56,2.56],color=muted,ls=(0,(4,3)),lw=1)
    for xx in [1.86,5.17,8.35,11.39]:arrow((xx,2.56),(xx,3.47),color=muted,lw=1,style=(0,(4,3)))
    for xx in [14.90,16.30]:arrow((xx,2.56),(xx,2.80),color=muted,lw=1,style=(0,(4,3)))
    arrow((8.35,2.56),(8.35,2.19),color=muted,lw=1,style=(0,(4,3)))
    export(fig,'Supp_FigureS1')


    (folder/'figure_manifest.json').write_text(json.dumps(records,indent=2))
    assert len(records)==10
