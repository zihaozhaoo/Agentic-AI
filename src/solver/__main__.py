import os
import pprint

import yaml

from .or_tools import cost_estimator
from ..data_gen.sf_dummy import simulation
from ..data_gen.nodify import create_network

# Configure Parameters
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'configs', 'data_generation.yaml'))
with open(config_path, 'r') as f:
    config = yaml.safe_load(f) or {}

or_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'configs', 'oracle.yaml'))
with open(or_config_path, 'r') as f:
    or_config = yaml.safe_load(f) or {}

# Simulation and Solver
requests, index_list = simulation(**config['sf_dummy'])
enc_net = create_network(requests)
res = cost_estimator(**or_config['or_tools'], distance_matrix=enc_net['distance'], requests=enc_net['requests'])

# Print Results
print(requests)
print(enc_net['map'])
pprint.pprint(res)
