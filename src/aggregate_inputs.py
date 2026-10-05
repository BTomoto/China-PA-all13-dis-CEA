import pandas as pd
from _model_resources import table
from public_inputs import read_public_parent
from model_io import install
install()

def read_parent(name):
    if name!='PA_binary_20plus':
        return read_public_parent(name)
    record=table(name)
    return pd.DataFrame(record['data'],columns=record['columns'])
