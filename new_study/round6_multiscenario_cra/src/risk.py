import math
from .common import InputBlocked
from .exposure import validate_atoms

def validate_domain(unit,domain,energy):
    if (unit,domain,energy)!=('MET-min/week','total','gross'):raise InputBlocked('BLOCKED_EXPOSURE_UNIT_DOMAIN')

def categorical_pif(p0,p1,rr):
    if len(p0)!=len(p1) or len(p0)!=len(rr) or not rr:raise ValueError('category dimensions')
    for p in [p0,p1]:
        if any(not math.isfinite(v) or v<0 for v in p) or not math.isclose(sum(p),1,abs_tol=1e-10):raise ValueError('category weights')
    if any(not math.isfinite(r) or r<=0 for r in rr):raise ValueError('invalid RR')
    e0=sum(p*r for p,r in zip(p0,rr));e1=sum(p*r for p,r in zip(p1,rr))
    return (e0-e1)/e0

def continuous_pif(baseline,scenario,risk_function):
    b=validate_atoms(baseline);s=validate_atoms(scenario)
    risks=[risk_function(x) for x,_ in b+s]
    if any(not math.isfinite(r) or r<=0 for r in risks):raise ValueError('invalid dose risk')
    e0=sum(w*risk_function(x) for x,w in b);e1=sum(w*risk_function(x) for x,w in s)
    return (e0-e1)/e0

def published_grid_risk(dose,rows,*,permit_linear_interpolation=False):
    """Exact published knots; no tails or spline coefficients invented."""
    grid=sorted((float(r['dose']),float(r['estimate'])) for r in rows)
    if dose<grid[0][0] or dose>grid[-1][0]:raise InputBlocked('BLOCKED_RR_OUTSIDE_PUBLISHED_SUPPORT')
    for x,y in grid:
        if dose==x:return y
    if not permit_linear_interpolation:raise InputBlocked('BLOCKED_RR_INTERPOLATION_NOT_ADMITTED')
    # Explicit numerical sensitivity only, never the original Bayesian spline.
    for (a,ra),(b,rb) in zip(grid,grid[1:]):
        if a<dose<b:return ra+(rb-ra)*(dose-a)/(b-a)
    raise ValueError('invalid dose')

def category_identification_bounds(p,alpha,rr):
    """Algebraic envelope over UNKNOWN active-category proportions.

    No actual active distribution is constructed. The categorical model assigns
    each category its published RR, a structural sensitivity, not exact-dose RR.
    """
    if not 0<=p<=1 or not 0<=alpha<=1 or len(rr)!=4 or rr[0]!=1 or any(r<=0 or r>1 for r in rr):raise ValueError('invalid category bound inputs')
    numerator=alpha*p*(1-rr[1])
    return numerator/(p+(1-p)*max(rr[1:])),numerator/(p+(1-p)*min(rr[1:]))

def map_incidence(baseline,pif,endpoint_admission):
    if endpoint_admission!='ADMIT_MATCHED_INCIDENCE':raise InputBlocked('BLOCKED_ENDPOINT_ALIGNMENT')
    if pif is None:raise InputBlocked('BLOCKED_EXPOSURE_DISTRIBUTION')
    if not math.isfinite(baseline) or baseline<0 or not math.isfinite(pif) or not 0<=pif<=1:raise ValueError('invalid incidence mapping')
    return baseline*pif

def map_other_outcome(*args,**kwargs):raise InputBlocked('BLOCKED_OUTCOME_RISK_MAPPING')
