"""Deterministic weighted pushforwards; no China activity distribution is imputed."""
import math
from .common import InputBlocked

def validate_atoms(atoms):
    if atoms is None:raise InputBlocked('BLOCKED_EXPOSURE_DISTRIBUTION')
    atoms=list(atoms)
    if not atoms or any(not math.isfinite(x) or not math.isfinite(w) or x<0 or w<0 for x,w in atoms):raise ValueError('invalid activity/weight')
    if not math.isclose(sum(w for _,w in atoms),1,abs_tol=1e-10):raise ValueError('weights must sum to one')
    return atoms

def completion(year,path):
    if path=='immediate_2025':return 1.
    if path=='common_2030':return min(1.,max(0.,(year-2025)/5))
    if path in ['baseline','gradual_2030']:return 1.
    raise ValueError('unknown implementation path')

def p15_mover_fraction(year):return .15*min(1.,max(0.,(year-2025)/5))

def transformed_distribution(atoms,scenario,year,path):
    atoms=validate_atoms(atoms)
    if scenario=='B0':return atoms.copy()
    if scenario not in ['P15','R1','R2','R3']:raise ValueError('unknown scenario')
    full=[]
    for x,w in atoms:
        if scenario=='P15':
            alpha=p15_mover_fraction(year) if x<600 else 0.
            full.extend([(x,w*(1-alpha)),(600.,w*alpha)])
        elif scenario=='R1':full.append((max(x,600.),w))
        elif scenario=='R2':full.append((1.2*x,w))
        else:full.append((600. if x<600 else 1.2*x,w))
    c=completion(year,path) if scenario.startswith('R') else 1.
    result=[(x,w*(1-c)) for x,w in atoms]+[(x,w*c) for x,w in full]
    return validate_atoms(result)

def inactive_share(atoms):return sum(w for x,w in validate_atoms(atoms) if x<600)

def known_inactive_share(p,scenario,year,path):
    if not 0<=p<=1:raise ValueError('invalid inactive prevalence')
    if scenario=='B0':return p
    if scenario=='P15':return p*(1-p15_mover_fraction(year))
    if scenario in ['R1','R3']:return p*(1-completion(year,path))
    if scenario=='R2':return p if completion(year,path)==0 else None
    raise ValueError('unknown scenario')
