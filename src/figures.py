import io
from model_io import write_encoded
from model_io import install as _configure_io
_configure_io()
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reporting import AGES, DISEASES, save

EN=dict(zip(DISEASES,['IHD','Stroke','Type 2 diabetes','Hypertension','Depression','Dementia','Bladder','Breast','Colorectal','Endometrial','Esophageal','Stomach','Kidney']))
EN['cancer']='Cancer'

def finish(root,fig,name):
    folder=root/'outputs/figures';folder.mkdir(parents=True,exist_ok=True)
    if name.startswith('Main_Figure1'):
        for ext in ['png','pdf']:
            buf=io.BytesIO()
            fig.savefig(buf,format=ext,dpi=220,bbox_inches='tight')
            write_encoded(folder/f'{name}.{ext}.pae',buf.getvalue())
    else:
        fig.savefig(folder/f'{name}.png',dpi=220,bbox_inches='tight')
        fig.savefig(folder/f'{name}.pdf',bbox_inches='tight')
    plt.close(fig)

def baseline(root,frame,name,title):
    fig,axes=plt.subplots(1,2,figsize=(12,4),sharey=True,layout='constrained')
    for ax,sex in zip(axes,['Female','Male']):
        d=frame[frame.sex.eq(sex)].set_index('age_group').reindex(AGES)
        ax.bar(AGES,d.p_inactive*100,label='Insufficient',color='#c87c66')
        ax.bar(AGES,(1-d.p_inactive)*100,bottom=d.p_inactive*100,label='Meets recommendation',color='#426c90')
        ax.set(title=sex,ylim=(0,100),xlabel='Age');ax.tick_params(axis='x',rotation=45)
    axes[0].set_ylabel('Percentage');axes[1].legend(loc='upper left',bbox_to_anchor=(0,1.21),ncol=2,frameon=False)
    fig.suptitle(title);finish(root,fig,name)

def build_figures(root):
    root=Path(root);out=root/'outputs';plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    # Figure 1 retains the published aggregate baseline for comparison only.
    b=pd.read_csv(root/'reference/parameter_tables/S03_as_reported.csv')
    b.columns=['sex','age_group','population_million','p_inactive','p_active']
    b['sex']=b.sex.map({'女性':'Female','男性':'Male'});b['age_group']=b.age_group.str.replace('–','-',regex=False).replace({'≥70':'70+'})
    b['p_inactive']=b.p_inactive.str.rstrip('%').astype(float)/100
    save(root,'figure_data/Main_Figure1_published_aggregate.csv',b)
    baseline(root,b,'Main_Figure1_published_aggregate','Published aggregate baseline (not the formal model input)')
    actual=pd.read_csv(out/'model_baseline_age_sex.csv')
    baseline(root,actual,'Main_Figure1_formal_model_baseline','Frozen formal-model baseline')
    s29=pd.read_csv(out/'tables/S29.csv')
    s29['condition']=np.where(s29.outcome_id.str.endswith('_cancer'),'cancer',s29.outcome_id)
    group=s29.groupby('condition')[['avoided_value','discounted_savings_main_2025_cny']].sum()
    save(root,'figure_data/Main_Figure2_groups.csv',group.reset_index())
    cancer=s29[s29.outcome_id.str.endswith('_cancer')].set_index('outcome_id')[['avoided_value','discounted_savings_main_2025_cny']]
    save(root,'figure_data/Main_Figure2_cancer.csv',cancer.reset_index())
    fig,ax=plt.subplots(4,2,figsize=(13,17),layout='constrained')
    for row,frame in [(0,group),(2,cancer)]:
        for col,(metric,scale,unit) in enumerate([('avoided_value',1e4 if row==0 else 1,'Disease quantity (10,000 units)' if row==0 else 'Incident cancer cases'),('discounted_savings_main_2025_cny',1e8,'Direct medical savings (CNY 100 million)')]):
            v=frame[metric].sort_values(ascending=False)
            labels=[EN[x] for x in v.index]
            colors=plt.cm.Set2(np.linspace(0,1,len(v)))
            wedges,_=ax[row,col].pie(v,colors=colors,wedgeprops={'width':.42},startangle=90)
            ax[row,col].legend(wedges,[f'{l} {100*n/v.sum():.2f}%' for l,n in zip(labels,v)],loc='center left',bbox_to_anchor=(.9,.5),fontsize=8,frameon=False)
            ax[row,col].set_title(chr(65+row*2+col)+'. '+('Quantity composition' if col==0 else 'Medical savings composition'))
            ax[row+1,col].bar(labels,v/scale,color=colors)
            ax[row+1,col].set_ylabel(unit);ax[row+1,col].tick_params(axis='x',rotation=35)
            ax[row+1,col].set_title(chr(65+(row+1)*2+col)+'. Absolute quantities')
    finish(root,fig,'Main_Figure2')
    health=pd.read_csv(out/'disease_age_sex_health.csv');qty=pd.read_csv(out/'disease_age_sex_quantity.csv');medical=pd.read_csv(out/'age_sex_disease_medical_10y.csv')
    dfs=[medical,health[health.horizon_years.eq(10)&health.measure_short.eq('DALY')],qty[qty.horizon_years.eq(10)]]
    cols=['medical_savings_2025_cny','discounted_value','avoided_value'];scales=[1e9,1e6,1e6]
    labels=['Direct medical savings (CNY bn)','DALYs averted (million)','Disease quantity (million units)']
    fig,axs=plt.subplots(1,3,figsize=(15,7),sharey=True,layout='constrained')
    colors=dict(zip(DISEASES,plt.cm.tab20(np.linspace(0,1,len(DISEASES)))))
    for i,(ax,d,c,scale,label) in enumerate(zip(axs,dfs,cols,scales,labels)):
        p=d.pivot_table(index='age_group',columns='outcome_id',values=c,aggfunc='sum').reindex(AGES).fillna(0)
        save(root,f'figure_data/Main_Figure3_panel{i+1}.csv',p.reset_index())
        left=np.zeros(len(AGES))
        for dis in DISEASES:
            if dis not in p:continue
            v=p[dis].to_numpy()/scale;ax.barh(AGES,v,left=left,label=EN[dis],color=colors[dis]);left+=v
        ax.set_xlabel(label);ax.set_title(chr(65+i))
    axs[2].legend(loc='center left',bbox_to_anchor=(1,.5),fontsize=8,frameon=False)
    finish(root,fig,'Main_Figure3')
    trajectory=pd.read_csv(out/'annual_cumulative_economic_trajectory.csv')
    fig,axs=plt.subplots(2,1,figsize=(11,8),layout='constrained')
    for ax,metric,color in zip(axs,['medical','gdp_equivalent'],['#5686a2','#8a75a1']):
        ax.bar(trajectory.year,trajectory[f'annual_{metric}_bn'],color=color,label='Annual')
        ax.set_ylabel('Annual (2025 CNY bn)');ax.set_xlabel('Year')
        twin=ax.twinx();twin.plot(trajectory.year,trajectory[f'cumulative_{metric}_bn'],color='#b64f64',label='Cumulative')
        twin.set_ylabel('Cumulative (2025 CNY bn)');ax.axvspan(2034.5,2050.5,color='grey',alpha=.08)
        ax.set_title('Direct medical savings' if metric=='medical' else 'GDP-equivalent productivity gain')
    finish(root,fig,'Main_Figure4')
    asset=root/'reference/Supp_FigureS1_model_diagram.png'
    if asset.exists():shutil.copy2(asset,out/'figures/Supp_FigureS1_static_diagram.png')
    front=pd.read_csv(out/'tables/S20.csv')
    fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,h in zip(axs,[5,10]):
        g=front[front.horizon_years.eq(h)]
        ax.scatter(g.mean_discounted_dalys/1e6,g.mean_cost_2025_cny/1e9,color='grey')
        f=g[g.frontier_status.eq('FRONTIER')].sort_values('mean_discounted_dalys')
        ax.plot(f.mean_discounted_dalys/1e6,f.mean_cost_2025_cny/1e9,'o-',color='#af5362')
        for r in g.itertuples():ax.annotate(r.scenario_id,(r.mean_discounted_dalys/1e6,r.mean_cost_2025_cny/1e9),xytext=(3,4),textcoords='offset points')
        ax.set(title=f'{h}-year',xlabel='Mean DALYs averted (million)',ylabel='Mean programme cost (CNY bn)')
    finish(root,fig,'Supp_FigureS2')
    ceac=pd.read_csv(out/'tables/S22.csv')
    fig,axs=plt.subplots(1,2,figsize=(11,4),sharey=True,layout='constrained')
    for ax,h in zip(axs,[5,10]):
        for s,g in ceac[ceac.horizon_years.eq(h)].groupby('scenario_id'):ax.plot(g.wtp_cny_per_daly,g.probability_cost_effective,'o-',label=s)
        ax.set(title=f'{h}-year',xlabel='WTP (CNY/DALY)',ylim=(0,1));ax.legend(frameon=False,ncol=2,fontsize=8)
    axs[0].set_ylabel('Probability optimal');finish(root,fig,'Supp_FigureS3')
    pair=pd.read_csv(out/'figure_data/S0_S6_CEAC.csv');restricted=pd.read_csv(out/'figure_data/restricted_S1_S5_CEAC.csv')
    fig,axs=plt.subplots(2,2,figsize=(12,8),sharey=True,layout='constrained')
    for i,h in enumerate([5,10]):
        p=pair[pair.horizon_years.eq(h)]
        for s in ['S0','S6']:axs[i,0].plot(p.wtp,p[s+'_probability'],label=s)
        for s,g in restricted[restricted.horizon_years.eq(h)].groupby('scenario_id'):axs[i,1].plot(g.wtp,g.probability,label=s)
        g=restricted[restricted.horizon_years.eq(h)].drop_duplicates('wtp')
        axs[i,1].plot(g.wtp,g.ceaf_probability,'k--',linewidth=.8,label='CEAF')
        for ax in axs[i]:ax.set(title=f'{h}-year',xlabel='WTP (CNY/DALY)',ylabel='Probability optimal',ylim=(0,1.03));ax.legend(frameon=False,fontsize=8)
    finish(root,fig,'Supp_FigureS4')
    m=pd.read_csv(out/'tables/S24.csv');m=m[m.horizon_years.eq(10)].sort_values('discounted_savings_main_2025_cny')
    fig,axs=plt.subplots(1,2,figsize=(13,6),layout='constrained')
    axs[0].barh([EN[x] for x in m.outcome_id],m.discounted_savings_main_2025_cny/1e9,color='#2b8490');axs[0].set_xlabel('Direct medical savings (CNY bn)')
    axs[1].plot(trajectory.year,trajectory.cumulative_medical_bn,label='Direct medical savings');axs[1].plot(trajectory.year,trajectory.cumulative_gdp_equivalent_bn,label='GDP-equivalent gain')
    axs[1].set(xlabel='Year',ylabel='Cumulative (2025 CNY bn)');axs[1].legend(frameon=False,fontsize=9)
    finish(root,fig,'Supp_FigureS5')
    conv=pd.read_csv(out/'figure_data/convergence.csv');rows=[]
    fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
    for metric,g in conv.groupby('metric'):
        g=g.sort_values('checkpoint_draws').copy();g['deviation_percent']=(g.cumulative_mean/g.cumulative_mean.iloc[-1]-1)*100;rows.append(g)
        ax.plot(g.checkpoint_draws,g.deviation_percent,'o-',label=metric.replace('discounted_','').replace('_2025_cny','').replace('_',' '))
    ax.set(xscale='log',xlabel='Cumulative draws',ylabel='Deviation from 10,000-draw mean (%)');ax.axhline(0,color='grey',linewidth=.6);ax.legend(frameon=False,fontsize=8)
    finish(root,fig,'Supp_FigureS6');save(root,'figure_data/convergence_deviation.csv',pd.concat(rows,ignore_index=True))
    print('Exported main Figures 1–4 and Supplement Figures S1–S6.')
