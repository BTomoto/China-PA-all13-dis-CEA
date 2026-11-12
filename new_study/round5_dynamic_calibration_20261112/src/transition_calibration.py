"""Joint incidence/prevalence/mortality consistency fit; never admits D/P by itself.

Calibration uses a stationary synthetic-age profile, NOT a measured birth cohort.
GBD incidence is per total population: i_s(a)=I(a)/(1-p_model(a)).
S'=-(i_s+o)S; D'=i_s*S-(f+o)D; hence p'=I-f*p*(1-p).
Equal other mortality cancels in prevalence, but stays in the state equations.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import least_squares
from .common import AGES,config

CENTERS=np.arange(22.5,98,5,dtype=float)

def profile(log_f,p_start,incidence,step=.5):
    """Deterministic RK4; log-PCHIP gives positive C1 case-fatality by age."""
    grid=np.arange(CENTERS[0],CENTERS[-1]+step/2,step/2)
    f=np.exp(PchipInterpolator(CENTERS,log_f)(grid))
    inc=np.interp(grid,CENTERS,incidence)
    values=[float(p_start)];p=float(p_start)
    per_segment=round(5/step)
    def derivative(p,j):return inc[j]-f[j]*p*(1-p)
    for n in range(round(75/step)):
        j=2*n
        k1=derivative(p,j);k2=derivative(p+step*k1/2,j+1)
        k3=derivative(p+step*k2/2,j+1);k4=derivative(p+step*k3,j+2)
        p+=step*(k1+2*k2+2*k3+k4)/6
        if (n+1)%per_segment==0:values.append(p)
    return np.asarray(values)

def fit_one(disease,sex,datasets):
    settings=config()['calibration']
    inc=np.array([datasets['incidence'][(disease,sex,a,'Incidence','Rate')]/1e5 for a in AGES])
    prevalence=np.array([datasets['disease'][(disease,sex,a,'Prevalence','Rate')]/1e5 for a in AGES])
    mortality=np.array([datasets['disease'][(disease,sex,a,'Deaths','Rate')]/1e5 for a in AGES])
    all_m=np.array([datasets['all_cause'][('ALL',sex,a,'Deaths','Rate')]/1e5 for a in AGES])
    other=all_m-mortality
    if np.any(other<0):raise ValueError('negative other mortality')
    initial=mortality/prevalence
    def decode(theta):
        f=np.exp(theta[:-1]);p0=1/(1+np.exp(-theta[-1]))
        return f,profile(theta[:-1],p0,inc,settings['step_years'])
    def residual(theta):
        f,p=decode(theta)
        if np.any(p<=0) or np.any(p>=1):return np.full(46,1e6)
        return np.concatenate([np.log(p/prevalence),np.log(f*p/mortality),np.sqrt(settings['smoothness_weight'])*np.diff(theta[:-1],n=2)])
    theta=np.r_[np.log(initial),np.log(prevalence[0]/(1-prevalence[0]))]
    fits=[]
    for start in [theta,np.r_[np.full(16,np.mean(np.log(initial))),theta[-1]]]:
        fits.append(least_squares(residual,start,bounds=(np.r_[np.full(16,-16),-16],np.r_[np.full(16,2),4]),max_nfev=settings['max_nfev'],ftol=1e-10,xtol=1e-10,gtol=1e-9))
    best=min(fits,key=lambda x:np.sum(x.fun**2));f,p=decode(best.x)
    initial_p=profile(np.log(initial),prevalence[0],inc,settings['step_years'])
    fine=profile(best.x[:-1],p[0],inc,settings['step_years']/2)
    params=[];diagnostics=[]
    errors=[]
    for index,age in enumerate(AGES):
        for measure,target,fitted in [('Incidence',inc[index],inc[index]),('Prevalence',prevalence[index],p[index]),('Deaths',mortality[index],f[index]*p[index]),('All_cause_deaths',all_m[index],other[index]+f[index]*p[index])]:
            relative=(fitted-target)/target
            diagnostics.append(dict(disease=disease,sex=sex,age=age,measure=measure,target_rate_per_100k=target*1e5,fitted_rate_per_100k=fitted*1e5,absolute_error=abs(fitted-target)*1e5,relative_error=relative,status='PASS' if abs(relative)<=settings['maximum_relative_error'] else 'FAIL'))
            if measure in ['Prevalence','Deaths']:errors.append(relative)
        params.append(dict(disease=disease,sex=sex,age=age,initial_deaths_over_prevalence=initial[index],calibrated_case_fatality_hazard=f[index],remission_hazard=0,recurrence_state=False,initial_ratio_prevalence_fitted=initial_p[index],fitted_prevalence=p[index],target_prevalence=prevalence[index],target_death_hazard=mortality[index],fitted_population_death_hazard=f[index]*p[index],integration_half_step_difference=abs(p[index]-fine[index]),source='Joint GBD2023 fit; log-PCHIP; no direct D/P admission',admission_status='PENDING_GATE'))
    maxerr=float(np.max(np.abs(errors)));rms=float(np.sqrt(np.mean(np.array(errors)**2)))
    passed=bool(best.success and maxerr<=settings['maximum_relative_error'] and rms<=settings['rms_relative_error'])
    # Necessary bound: without remission and with nonnegative case death,
    # prevalence growth cannot exceed cumulative total-population incidence.
    infeasible=[]
    for j in range(15):
        growth=prevalence[j+1]-prevalence[j]
        bound=5*(inc[j]+inc[j+1])/2
        if growth>bound+1e-10:
            infeasible.append(dict(from_age=AGES[j],to_age=AGES[j+1],prevalence_increase=growth,maximum_increase_without_target_deaths=bound,excess=growth-bound))
    for row in params:row['admission_status']='CALIBRATED_PROVISIONAL' if passed else 'BLOCKED_TRANSITION_CALIBRATION'
    summary=dict(disease=disease,sex=sex,status='PASS' if passed else 'FAIL',optimizer_success=bool(best.success),optimizer_message=best.message,nfev=int(best.nfev),maximum_relative_error=maxerr,rms_relative_error=rms,cost=float(best.cost),integration_half_step_max_difference=float(np.max(np.abs(p-fine))),structurally_incompatible_age_intervals=infeasible,initial_ratio_joint_log_residual_norm=float(np.linalg.norm(np.r_[np.log(initial_p/prevalence),np.log(initial*initial_p/mortality)])),fitted_joint_log_residual_norm=float(np.linalg.norm(best.fun[:32])),calibration_scope='stationary_age_profile_22.5_to_97.5; 95+ representative age approximation; temporal cohort effects unidentified')
    return params,diagnostics,summary

def calibrate(datasets):
    parameters=[];diagnostics=[];summaries=[]
    for disease in ['IHD','IS']:
        for sex in ['Male','Female']:
            p,d,s=fit_one(disease,sex,datasets);parameters+=p;diagnostics+=d;summaries.append(s)
    passed=all(s['status']=='PASS' for s in summaries)
    return parameters,diagnostics,dict(status='DYNAMIC_PILOT_PROVISIONAL' if passed else 'BLOCKED_TRANSITION_CALIBRATION',thresholds=config()['calibration'],groups=summaries,all_groups_pass=passed,limitations=['No historical cohort path was identified by these 2023 exports','No remission; same other-cause mortality in both live states','95+ calibration midpoint is approximate; terminal cohort simulation remains open','Thresholds are pre-fit computational screens requiring Work review, not validated goodness-of-fit standards'])
