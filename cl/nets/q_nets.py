import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

from nets.custom_layers import Linear_noisy, parallel_Linear
from nets.vision_nets import vision_Net
from nets.net_utils import weights_init_rnd

use_cuda = torch.cuda.is_available()
device   = torch.device("cuda" if use_cuda else "cpu")


# Continuous action space
#-------------------------------------------------
class q_Net(nn.Module):
    def __init__(self, s_dim, a_dim, noisy=False, lr=3e-4):
        super().__init__() 
        self.s_dim = s_dim
        self.a_dim = a_dim

        if noisy:
            layer = Linear_noisy
        else:
            layer = nn.Linear

        self.l1 = layer(s_dim+a_dim, 256)
        self.l2 = layer(256, 256)
        self.lQ = layer(256, 1)
        
        if not noisy:
            self.apply(weights_init_rnd)
            torch.nn.init.orthogonal_(self.lQ.weight, 0.01)
            self.lQ.bias.data.zero_()
        else:
            torch.nn.init.orthogonal_(self.lQ.mean_weight, 0.01)
            self.lQ.mean_bias.data.zero_()

        self.optimizer = Adam(self.parameters(), lr=lr)
        
    def forward(self, s, a):
        sa = torch.cat([s,a], dim=1)        
        x = F.relu(self.l1(sa))
        x = F.relu(self.l2(x))
        Q = self.lQ(x)        
        return Q


# Discrete action space
#-------------------------------------------------
class multihead_dueling_q_Net(nn.Module):
    def __init__(self, s_dim, n_actions, n_heads):
        super().__init__() 
        self.s_dim = s_dim
        self.n_actions = n_actions

        self.l1 = parallel_Linear(n_heads, s_dim, 256)
        self.l2 = parallel_Linear(n_heads, 256, 256)
        self.lV = parallel_Linear(n_heads, 256, 1)
        self.lA = parallel_Linear(n_heads, 256, n_actions)
        
        self.apply(weights_init_rnd)
        torch.nn.init.orthogonal_(self.lV.weight, 0.01)
        self.lV.bias.data.zero_()
        torch.nn.init.orthogonal_(self.lA.weight, 0.01)
        self.lA.bias.data.zero_()
        
    def forward(self, s):        
        x = F.relu(self.l1(s))
        x = F.relu(self.l2(x))
        V = self.lV(x)        
        A = self.lA(x)
        Q = V + A - A.mean(2, keepdim=True) 
        return Q


class vision_multihead_dueling_q_Net(multihead_dueling_q_Net):
    def __init__(self, s_dim, latent_dim, n_actions, n_heads, lr=1e-4):
        super().__init__(s_dim + latent_dim, n_actions, n_heads)
        self.vision_nets = nn.ModuleList([vision_Net(latent_dim=latent_dim, 
            noisy=False) for i in range(0, n_heads)])
        self._n_heads = n_heads
        
        self.optimizer = Adam(self.parameters(), lr=lr)
        
    def forward(self, inner_state, outer_state):    
        state = []
        for head in range(0, self._n_heads):
            head_features = self.vision_nets[head](outer_state)
            state.append(torch.cat([inner_state, head_features], dim=1))
        state = torch.stack(state, dim=1)
        x = F.relu(self.l1(state))
        x = F.relu(self.l2(x))
        V = self.lV(x)        
        A = self.lA(x)
        Q = V + A - A.mean(2, keepdim=True) 
        return Q