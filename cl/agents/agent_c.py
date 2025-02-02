import numpy as np

import torch
import torch.nn as nn

from policy_nets import s_Net
from agent_1l_mt import create_first_level_multitask_agent
from concept_nets import SA_concept_Net
from net_utils import freeze
from utils import numpy2torch as np2torch
from utils import time_stamp


def load_first_level_agent(env, load_id, noisy=True, load_best=True,
                MODEL_PATH='/home/researcher/Diego/Concept_Learning_minimal/saved_models/'
                ):
    first_level_agent = create_first_level_multitask_agent(env, noisy=noisy)    
    if load_best:
        first_level_agent.load(MODEL_PATH + 'best_', load_id)
    else:
        first_level_agent.load(MODEL_PATH, load_id)
    return first_level_agent


def create_conceptual_agent(env, load_id, n_concepts={'state': 10, 'action': 4}, load_best=True, 
                concept_net_type='SA', device='cuda', noisy=True):
    # Load first level agent
    first_level_agent = load_first_level_agent(env, load_id, load_best=load_best, noisy=noisy)

    # Generate concept network
    if concept_net_type == 'SA':
        if first_level_agent._type == 'multitask':
            # Identify dimensions
            s_dim = env.observation_space['state'].shape[0]
            t_dim = env.observation_space['task'].shape[0]
            a_dim = env.action_space.shape[0]
            
            concept_architecture = SA_concept_Net(s_dim+t_dim, n_concepts['state'], 
                                                    a_dim+t_dim, n_concepts['action'], noisy=noisy)

            conceptual_agent = conceptual_Agent(concept_architecture, first_level_agent, s_dim, a_dim, t_dim).to(device)
        else:
            raise RuntimeError('Invalid agent type')
    else:
        raise RuntimeError('Unkown concept network type')
    
    return concept_agent


class Conceptual_Agent(nn.Module):
    def __init__(self, concept_architecture, first_level_agent, s_dim, a_dim, t_dim):  
        super().__init__()    
        
        self.concept_architecture = concept_architecture
        self.first_level_agent = first_level_agent
        freeze(self.first_level_agent)

        self._s_dim = s_dim
        self._a_dim = a_dim
        self._t_dim = t_dim
        self._id = time_stamp()
    
    def forward(self, state_observations):
        actions_off = self.simulate(state_observations)
        action_observations = self.observe_action(state_observations, actions_off)
        PS_sT, log_PS_sT, PA_aT, log_PA_aT = \
            self.concept_architecture(state_observations, action_observations)
        return PS_sT, log_PS_sT, PA_aT, log_PA_aT
    
    def simulate(self, state_observations):
        return self.first_level_agent.architecture.actor.simulate(state_observations)

    def observe_action(self, state_observations, actions):
        tasks = state_observations[:,self._s_dim:]
        action_observations = np.concatenate((actions, tasks))
        return action_observations
   
    def save(self, save_path):
        torch.save(self.state_dict(), save_path + 'agent_2l_' + self._id)
    
    def load(self, load_directory_path, model_id, device='cuda'):
        dev = torch.device(device)
        self.load_state_dict(torch.load(load_directory_path + 'agent_2l_' + model_id, map_location=dev))


if __name__ == "__main__":
    agent = create_concept_agent()
    print("Successful second level agent creation")