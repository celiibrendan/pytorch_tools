import torch
from torch.nn import Linear
import torch.nn.functional as F
from torch_geometric.nn import GCNConv
from torch_geometric.nn import global_mean_pool,global_add_pool,global_mean_pool,global_sort_pool
import numpy as np
import torch as th
import torch.nn as nn
"""
Notes: 
Usually only have to use the batch variable when doing global pooling



"""
class Classifier(nn.Module):
    def __init__(
        self,
        n_classes,
        n_inputs,
        n_hidden = None,
        activation_function = "ReLU",
        n_hidden_layers = 1,
        f = True,
        use_bn = False,
        ):
        
        if n_hidden is None:
            n_hidden = 50
        super().__init__()
        self.act_func = activation_function
        hid_layers = []
        if n_hidden_layers==0:
            hid_layers.append(nn.Linear(n_inputs, n_classes))
        else:
            for i in range(n_hidden_layers):
                if i == 0:
                    input_stage = n_inputs
                else:
                    input_stage= n_hidden
                hid_layers += [nn.Linear(input_stage, n_hidden)]
                if use_bn:
                    hid_layers.append(nn.BatchNorm1d(n_hidden))
                hid_layers.append(nn.ReLU())

            hid_layers.append(nn.Linear(n_hidden, n_classes))
        self.classifier = nn.Sequential(*hid_layers
                                        )
        self.use_bn = use_bn

    def forward(self, x):
        return self.classifier(x)
    
class ClassifierFlat(nn.Module):
    def __init__(
        self,
        n_classes,
        n_inputs,
        dropout = 0.5,
        **kwargs
        ):
        self.lin = Linear(n_inputs, n_classes)
        self.dropout = dropout
        
    def forward(self,x):
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.lin(x)
        return x
        
    


# ---------------- basic graph neural network models -----------
# Define our GCN class as a pytorch Module
class GCNFlat(torch.nn.Module):
    def __init__(
        self, 
        n_hidden_channels,
        dataset_num_node_features,
        dataset_num_classes,
        n_layers = 3,
        activation_function = "relu",
        global_pool_type="mean",
                ):
        
        super(GCNFlat, self).__init__()
        # We inherit from pytorch geometric's GCN class, and we initialize three layers
        self.conv0 = GCNConv(dataset_num_node_features, n_hidden_channels)
        for i in range(1,n_layers):
            setattr(self,f"conv{i}",GCNConv(n_hidden_channels, n_hidden_channels))
        self.n_conv = n_layers
        
        # Our final linear layer will define our output
        self.lin = Linear(n_hidden_channels, dataset_num_classes)
        self.act_func = getattr(F,activation_function)
        self.global_pool_func = eval(f"global_{global_pool_type}_pool")
                
        
    def encode(self,data):
        x, edge_index = data.x, data.edge_index
        batch = getattr(data,"batch",None)
        
        if batch is None:
            batch = torch.zeros(x.shape[0],dtype=torch.int64)
        # 1. Obtain node embeddings 
        for i in range(self.n_conv):
            x = getattr(self,f"conv{i}")(x, edge_index)
            if i < self.n_conv-1:
                x = self.act_func(x)
                    
        # 2. Readout layer
        
        x = self.global_pool_func(x, batch)  # [batch_size, hidden_channels]
        return x
    
    def forward(self, data):
        x = self.encode(data)
        # 3. Apply a final classifier
        x = F.dropout(x, p=0.5, training=self.training)
        x = self.lin(x)
        return F.softmax(x,dim=1)



class GCN(torch.nn.Module):
    def __init__(
        self, 
        n_hidden_channels,
        dataset_num_node_features,
        dataset_num_classes,
        n_layers = 3,
        
        global_pool_type="mean",
        use_bn = True,
        #for classifier:
        n_hidden_layers_classifier = 0,
        activation_function = "relu",
        
        
                ):
        
        super(GCN, self).__init__()
        # We inherit from pytorch geometric's GCN class, and we initialize three layers
        self.conv0 = GCNConv(dataset_num_node_features, n_hidden_channels)
        self.bn0 = torch.nn.BatchNorm1d(n_hidden_channels)
        for i in range(1,n_layers):
            setattr(self,f"conv{i}",GCNConv(n_hidden_channels, n_hidden_channels))
            setattr(self,f"bn{i}",torch.nn.BatchNorm1d(n_hidden_channels))
        self.n_conv = n_layers
        
        # Our final linear layer will define our output
        #self.lin = Linear(n_hidden_channels, dataset_num_classes)
        self.act_func = getattr(F,activation_function)
        self.global_pool_func = eval(f"global_{global_pool_type}_pool")
        self.use_bn = use_bn
        
        
        
        self.classifier = Classifier(
            n_classes = dataset_num_classes,
            n_inputs = n_hidden_channels,
            n_hidden_layers = n_hidden_layers_classifier,
            activation_function=activation_function,
            use_bn=use_bn
        )
                
        
    def encode(self,data):
        x, edge_index = data.x, data.edge_index
        batch = getattr(data,"batch",None)
        
        if batch is None:
            batch = torch.zeros(x.shape[0],dtype=torch.int64)
        # 1. Obtain node embeddings 
        for i in range(self.n_conv):
            x = getattr(self,f"conv{i}")(x, edge_index)
            if i < self.n_conv-1:
                x = self.act_func(x)
                
            if self.use_bn:
                setattr(self,f"bn{i}", nn.BatchNorm1d(x.size(1)))#.to(self.device)
                x = getattr(self,f"bn{i}")(x)
                    
        # 2. Readout layer
        x = self.global_pool_func(x, batch)  # [batch_size, hidden_channels]
        return x
    
    def forward(self, data):
        x = self.encode(data)
        x = self.classifier(x)
#         # 3. Apply a final classifier
#         x = F.dropout(x, p=0.5, training=self.training)
#         x = self.lin(x)
        return F.softmax(x,dim=1)
    
    
# ---------- Graph Attention Network -------------
from torch_geometric.nn import GATConv
import torch.nn as nn

class GAT(nn.Module):
    """
    Source: https://github.com/marblet/GNN_models_pytorch_geometric/blob/master/models/gat.py
    """
    def __init__(
        self, 
        dataset_num_node_features, 
        dataset_num_classes,
        n_hidden_channels=10, 
        global_pool_type="mean",
        n_layers = 2,
        dropout=0.6,
        activation_function = "elu",
        
        #parameters for the GAT
        heads=2, 
        first_heads=None,
        output_heads=None,

    
        #--- parameters for size of classifier
        classifier_flat = False,
        classifier_n_hidden = None,):
        super(GAT, self).__init__()
        
        if first_heads is not None:
            conv0_heads = first_heads
        else:
            conv0_heads = heads
        self.conv0 = GATConv(dataset_num_node_features, n_hidden_channels,
                           heads=conv0_heads, dropout=dropout)
        
        self.act_func = getattr(F,activation_function)
        
        prev_heads = conv0_heads
        for i in range(1,n_layers):
            if output_heads is not None:
                convN_heads = output_heads
            else:
                convN_heads = heads
            setattr(self,f"conv{i}",GATConv(n_hidden_channels*prev_heads, n_hidden_channels,
                           heads=convN_heads, dropout=dropout))
            prev_heads = heads
            
        self.dropout = dropout
        if global_pool_type is not None:
            self.global_pool_func = eval(f"global_{global_pool_type}_pool")
        else:
            self.global_pool_func = None
            
        self.n_conv = n_layers
        
        if classifier_flat:
            classifier_class = ClassifierFlat
        else:
            classifier_class = Classifier
            
        self.classifier = classifier_class(
            n_classes = dataset_num_classes,
            n_inputs = n_hidden_channels*heads,
        )

    def reset_parameters(self):
        self.gc1.reset_parameters()
        self.gc2.reset_parameters()

    def encode(self,data):    
        x, edge_index = data.x, data.edge_index
        batch = getattr(data,"batch",None)
        
        if batch is None:
            batch = torch.zeros(x.shape[0],dtype=torch.int64)
            
        for i in range(self.n_conv):
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = getattr(self,f"conv{i}")(x, edge_index)
            if i < self.n_conv-1:
                x = self.act_func(x)
        
        if self.global_pool_func is not None:
            x = self.global_pool_func(x, batch)
        return x
    def forward(self, data):
        x = self.encode(data)
        x = self.classifier(x)
        return F.softmax(x,dim=1)


class GAT_old(nn.Module):
    """
    Source: https://github.com/marblet/GNN_models_pytorch_geometric/blob/master/models/gat.py
    """
    def __init__(
        self, 
        dataset_num_node_features, 
        dataset_num_classes,
        n_hidden_channels=8, 
        first_heads=8, 
        output_heads=1, 
        dropout=0.6,
        global_pool_type="mean"):
        super(GAT, self).__init__()
        self.gc1 = GATConv(dataset_num_node_features, n_hidden_channels,
                           heads=first_heads, dropout=dropout)
        self.gc2 = GATConv(n_hidden_channels*first_heads, dataset_num_classes,
                           heads=output_heads, dropout=dropout)
        self.dropout = dropout
        if global_pool_type is not None:
            self.global_pool_func = eval(f"global_{global_pool_type}_pool")
        else:
            self.global_pool_func = None

    def reset_parameters(self):
        self.gc1.reset_parameters()
        self.gc2.reset_parameters()

    def encode(self,data):    
        x, edge_index = data.x, data.edge_index
        batch = getattr(data,"batch",None)
        
        if batch is None:
            batch = torch.zeros(x.shape[0],dtype=torch.int64)
            
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.gc1(x, edge_index)
        x = F.elu(x)
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.gc2(x, edge_index)
        if self.global_pool_func is not None:
            x = self.global_pool_func(x, batch)
        return x
    def forward(self, data):
        x = self.encode(data)
        return F.softmax(x,dim=1)
    
    
class BatchedGraphSAGE(nn.Module):
    def __init__(
        self, 
        infeat, 
        outfeat,
        device='cpu',
        use_bn=True, 
        mean=False, 
        add_self=False):
        
        super().__init__()
        self.add_self = add_self
        self.use_bn = use_bn
        self.device = device
        self.mean = mean
        self.W = nn.Linear(infeat, outfeat, bias=True)
        nn.init.xavier_uniform_(self.W.weight, gain=nn.init.calculate_gain('relu'))

    def forward(
        self,
        #data
        x,
        adj,
        mask = None,
        ):
        #x,adj,mask = data.x, data.adj, data.mask
        if self.add_self:
            adj = adj + torch.eye(adj.size(0)).to(self.device)

        if self.mean:
            adj = adj / adj.sum(1, keepdim=True)

        h_k_N = torch.matmul(adj, x)
        h_k = self.W(h_k_N)
        h_k = F.normalize(h_k, dim=2, p=2)
        h_k = F.relu(h_k)
        if self.use_bn:
            self.bn = nn.BatchNorm1d(h_k.size(1)).to(self.device)
            h_k = self.bn(h_k)
        if mask is not None:
            h_k = h_k * mask.unsqueeze(2).expand_as(h_k)
        return h_k
    
    
class GraphSAGE(nn.Module):
    dense_adj = True
    
    def __init__(
        self,
        dataset_num_node_features, 
        dataset_num_classes,
        n_layers = 2,
        n_hidden_channels=8, 
        #dropout=0.6,
        global_pool_type="mean",
        
        
        #parameters for the individual GraphSAGEs
        device = "cpu",
        use_bn=False, 
        mean=False, 
        add_self=False,
        
        #--- parameters for size of classifier
        classifier_n_hidden = None,
        ):
        
        super(GraphSAGE, self).__init__()
        
        self.conv0 = BatchedGraphSAGE(
            dataset_num_node_features,
            n_hidden_channels,
            device = device,
            use_bn=use_bn, 
            mean=mean, 
            add_self=add_self)
        
        for i in range(1,n_layers):
            setattr(self,f"conv{i}",BatchedGraphSAGE(
            n_hidden_channels,
            n_hidden_channels,
            device = device,
            use_bn=use_bn, 
            mean=mean, 
            add_self=add_self))
            
        self.n_conv = n_layers
        
        #self.act_func = getattr(F,activation_function)
        self.global_pool_type = global_pool_type
        
        self.classifier = Classifier(
            n_classes = dataset_num_classes,
            n_inputs = n_hidden_channels,
            n_hidden = classifier_n_hidden,
        )
        
    def encode(self,data):
        x,adj,mask = data.x, data.adj, data.mask
        
        for i in range(self.n_conv):
            if mask.shape[1] == x.shape[1]:
                x = getattr(self,f"conv{i}")(x, adj, mask)
            else:
                x = getattr(self,f"conv{i}")(x, adj)
            
        x = x * mask.reshape(*mask.shape,1)
        #readout_x = self.global_pool_func(x, batch)  # [batch_size, hidden_channels]
        readout_x = getattr(x,self.global_pool_type)(dim=1)
        return readout_x
    
    def forward(self, data):
        graph_feat = self.encode(data)
        output = self.classifier(graph_feat)
        return F.softmax(output, dim=-1)
    
        
    

    
# --------------------- ALL OF THE DIFFPOOL MODELS -------------

    
# ---- simple diff pool -------------
"""
Source: https://github.com/AntonioLonga/PytorchGeometricTutorial/blob/main/Tutorial16/Tutorial16.ipynb

Note: This requires the data to be a dense matrix 
1. so need to T.ToDense() transform
2. and the DenseDataLoader

-- Still had bugs and couldn't get to work


"""


from torch_geometric.nn import DenseGCNConv as DenseGCNConv, dense_diff_pool
class DiffPoolSimpleGNN(torch.nn.Module):
    def __init__(
        self,
        in_channels,
        hidden_channels,
        out_channels,
        normalize=False,
        lin=True,
        activation_function = "relu",
        use_bn = True,):
        super(DiffPoolSimpleGNN, self).__init__()
        
        self.convs = torch.nn.ModuleList()
        self.bns = torch.nn.ModuleList()
        
        self.convs.append(DenseGCNConv(in_channels, hidden_channels, normalize))
        self.bns.append(torch.nn.BatchNorm1d(hidden_channels))
        
        self.convs.append(DenseGCNConv(hidden_channels, hidden_channels, normalize))
        self.bns.append(torch.nn.BatchNorm1d(hidden_channels))
        
        self.convs.append(DenseGCNConv(hidden_channels, out_channels, normalize))
        self.bns.append(torch.nn.BatchNorm1d(out_channels))
        
        self.act_func = getattr(F,activation_function)
        
        self.use_bn = use_bn


    def forward(self, x=None,adj = None,mask=None,data=None):
        if x is None:
            x,adj,mask = data.x,data.adj,data.mask
            
        
        
        for step in range(len(self.convs)):
            x = F.relu(self.convs[step](x, adj, mask))
            if self.use_bn:
                self.bns[step] = nn.BatchNorm1d(x.size(1))#.to(self.device)
                x = self.bns[step](x)
        
        return x
from math import ceil
class DiffPoolSimple(torch.nn.Module):
    def __init__(
        self,
        dataset_num_node_features, 
        dataset_num_classes,
        n_hidden_channels=64, 
        max_nodes=150,
        pool_ratio = 0.25,
        n_pool_layers = 2,
        
        #classifier arguments
        classifier_n_hidden = 50,
        global_pool_type="mean"
        
        ):
        super(DiffPoolSimple, self).__init__()
        self.global_pool_type = global_pool_type
#         if max_nodes > dataset_num_node_features:
#             max_nodes = dataset_num_node_features
        
        num_nodes = ceil(pool_ratio * max_nodes)
        if num_nodes < 1:
            num_nodes = 1
        
        self.n_nodes_by_layer = [dataset_num_node_features]
        self.n_pool_layers = n_pool_layers
        
        for i in range(n_pool_layers):
            self.n_nodes_by_layer.append(num_nodes)
            if i == 0:
                input_size = dataset_num_node_features
            else:
                input_size = n_hidden_channels
                
            #self.gnn1_pool = DiffPoolSimpleGNN(dataset_num_node_features, n_hidden_channels, num_nodes)
            setattr(self,f"gnn{i}_pool",DiffPoolSimpleGNN(input_size, n_hidden_channels, num_nodes))
            #self.gnn1_embed = DiffPoolSimpleGNN(dataset_num_node_features, n_hidden_channels, n_hidden_channels)
            setattr(self,f"gnn{i}_embed",DiffPoolSimpleGNN(input_size, n_hidden_channels, n_hidden_channels))

            num_nodes = ceil(pool_ratio * num_nodes)
            if num_nodes < 1:
                num_nodes = 1
    
                    
        #self.gnn3_embed = DiffPoolSimpleGNN(n_hidden_channels, n_hidden_channels, n_hidden_channels, lin=False)
        setattr(self,f"gnn{n_pool_layers}_embed",DiffPoolSimpleGNN(n_hidden_channels, n_hidden_channels, n_hidden_channels, lin=False))
        
        self.classifier = Classifier(
            n_classes = dataset_num_classes,
            n_inputs = n_hidden_channels,
            n_hidden = classifier_n_hidden,
        )

#         self.lin1 = torch.nn.Linear(n_hidden_channels, n_hidden_channels)
#         self.lin2 = torch.nn.Linear(n_hidden_channels, dataset_num_classes)

        
    def encode(self,data,return_loss = True):
        x,adj,mask = data.x, data.adj, data.mask
        
        gnn_loss = []
        cluster_loss = []
        for i in range(self.n_pool_layers):
            if i > 0:
                mask = None
                
            #s = self.gnn1_pool(x, adj, mask)
            s = getattr(self,f"gnn{i}_pool")(x, adj, mask)
            #x = self.gnn1_embed(x, adj, mask)
            x = getattr(self,f"gnn{i}_embed")(x, adj, mask)

            x, adj, l1, e1 = dense_diff_pool(x, adj, s, mask)
            gnn_loss.append(l1)
            cluster_loss.append(e1)
        #x_1 = s_0.t() @ z_0
        #adj_1 = s_0.t() @ adj_0 @ s_0

        x = getattr(self,f"gnn{self.n_pool_layers}_embed")(x, adj)

        x = getattr(x,self.global_pool_type)(dim=1)
        if return_loss:
            return x,np.sum(gnn_loss),np.sum(cluster_loss)
        else:
            return x
    def forward(self,data):
        x,gnn_loss,cluster_loss = self.encode(data,return_loss = True)
        x = self.classifier(x) 
        return F.softmax(x, dim=-1), gnn_loss, cluster_loss
    
    
# ----------- Graph Sage and Diff Pool ----------
"""
Official source: https://github.com/RexYing/diffpool

pyg implementation paper source = https://github.com/VoVAllen/diffpool
"""


class BatchedDiffPool(nn.Module):
    def __init__(
        self, 
        nfeat, 
        nnext, 
        nhid, 
        is_final=False,
        device='cpu', 
        link_pred=False):
        
        super(BatchedDiffPool, self).__init__()
        self.link_pred = link_pred
        self.device = device
        self.is_final = is_final
        self.embed = BatchedGraphSAGE(nfeat, nhid, device=self.device, use_bn=True)
        self.assign_mat = BatchedGraphSAGE(nfeat, nnext, device=self.device, use_bn=True)
        self.log = {}
        self.link_pred_loss = 0
        self.entropy_loss = 0

    def encode(
        self,
        x,
        adj,
        mask = None,):
        #x,adj,mask = data.x, data.adj, data.mask
        z_l = self.embed(x, adj)
        return z_l
    def cluster(
        self,
        x,
        adj,
        mask = None,):
        #x,adj,mask = data.x, data.adj, data.mask
        s_l = F.softmax(self.assign_mat(x, adj), dim=-1)
        return s_l
        
    def forward(
        self,
        #data,
        x,
        adj,
        mask = None,
        log=False):
        
        z_l = self.encode(x,adj,mask)
        s_l = self.cluster(x,adj,mask)
        if log:
            self.log['s'] = s_l.cpu().numpy()
        xnext = torch.matmul(s_l.transpose(-1, -2), z_l)
        anext = (s_l.transpose(-1, -2)).matmul(adj).matmul(s_l)
        if self.link_pred:
            # TODO: Masking padded s_l
            self.link_pred_loss = (adj - s_l.matmul(s_l.transpose(-1, -2))).norm(dim=(1, 2))
            self.entropy_loss = torch.distributions.Categorical(probs=s_l).entropy()
            if mask is not None:
                self.entropy_loss = self.entropy_loss * mask.expand_as(self.entropy_loss)
            self.entropy_loss = self.entropy_loss.sum(-1)
        return xnext, anext
    
    
class DiffPoolSAGE(nn.Module):
    def __init__(
        self,
        dataset_num_node_features, 
        dataset_num_classes,
        n_hidden_channels=64, 
        max_nodes=150,
        pool_ratio = 0.25,
        n_pool_layers = 2,
        device="cpu",
        link_pred=False,
        global_pool_type="mean",
        
        #classifier parameters
        classifier_n_hidden = 50):
        
        super().__init__()
        self.input_shape = dataset_num_node_features
        self.link_pred = link_pred
        self.device = device
        
        
        num_nodes = ceil(pool_ratio * max_nodes)
        if num_nodes < 1:
            num_nodes = 1
            
        self.n_nodes_by_layer = [dataset_num_node_features]
        self.n_pool_layers = n_pool_layers
        
        layers_list = []
        for i in range(n_pool_layers):
            self.n_nodes_by_layer.append(num_nodes)
            if i == 0:
                input_size = dataset_num_node_features
            else:
                input_size = n_hidden_channels
            layers_list.append(BatchedGraphSAGE(input_size,n_hidden_channels,device = self.device))
            layers_list.append(BatchedGraphSAGE(n_hidden_channels,n_hidden_channels,device = self.device))
            layers_list.append(BatchedDiffPool(n_hidden_channels, num_nodes, n_hidden_channels, device=self.device, link_pred=link_pred))
            
            num_nodes = ceil(pool_ratio * num_nodes)
            if num_nodes < 1:
                num_nodes = 1
            
        layers_list.append(BatchedGraphSAGE(n_hidden_channels,n_hidden_channels,device = self.device))
        layers_list.append(BatchedGraphSAGE(n_hidden_channels,n_hidden_channels,device = self.device))
        self.layers = nn.ModuleList(layers_list)
#         self.layers = nn.ModuleList([
#             BatchedGraphSAGE(dataset_num_node_features, 30, device=self.device),
#             BatchedGraphSAGE(30, 30, device=self.device),
#             BatchedDiffPool(30, pool_size, 30, device=self.device, link_pred=link_pred),
#             BatchedGraphSAGE(30, 30, device=self.device),
#             BatchedGraphSAGE(30, 30, device=self.device),
#             # BatchedDiffPool(30, 1, 30, is_final=True, device=self.device)
#         ])

        self.classifier = Classifier(
            n_classes = dataset_num_classes,
            n_inputs = n_hidden_channels,
            n_hidden = classifier_n_hidden,
        )
    
        self.global_pool_type = global_pool_type
        # writer.add_text(str(vars(self)))

    def encode(self,data):
        x,adj,mask = data.x, data.adj, data.mask
        
        for layer in self.layers:
            if isinstance(layer, BatchedGraphSAGE):
                if mask.shape[1] == x.shape[1]:
                    x = layer(x, adj, mask)
                else:
                    x = layer(x, adj)
            elif isinstance(layer, BatchedDiffPool):
                # TODO: Fix if condition
                if mask.shape[1] == x.shape[1]:
                    x, adj = layer(x, adj, mask)
                else:
                    x, adj = layer(x, adj)

        x = x * mask
        #readout_x = self.global_pool_func(x, batch)  # [batch_size, hidden_channels]
        readout_x = getattr(x,global_pool_type)(dim=1)
        return readout_x
    def forward(self, data):
        graph_feat = self.encode(data)
        output = self.classifier(graph_feat)
        return F.softmax(output, dim=-1)
        

    def loss(self, output, labels):
        criterion = nn.CrossEntropyLoss()
        loss = criterion(output, labels)
        if self.link_pred:
            for layer in self.layers:
                if isinstance(layer, BatchedDiffPool):
                    loss = loss + layer.link_pred_loss.mean() + layer.entropy_loss.mean()

        return loss
    
# --------------------- TREE LSTM MODEL ------------------------
"""
Tutorial: https://docs.dgl.ai/en/0.6.x/tutorials/models/2_small_graph/3_tree-lstm.html 

Code: https://github.com/dmlc/dgl/blob/master/examples/pytorch/tree_lstm/tree_lstm.py

Improved Semantic Representations From Tree-Structured Long Short-Term Memory Networks
https://arxiv.org/abs/1503.00075
"""
    

from collections import namedtuple
import dgl

class ChildSumTreeLSTMCell(nn.Module):
    def __init__(self, x_size, h_size):
        super(ChildSumTreeLSTMCell, self).__init__()
        self.W_iou = nn.Linear(x_size, 3 * h_size, bias=False)
        self.U_iou = nn.Linear(h_size, 3 * h_size, bias=False)
        self.b_iou = nn.Parameter(th.zeros(1, 3 * h_size))
        self.U_f = nn.Linear(h_size, h_size)

    def message_func(self, edges):
        return {'h': edges.src['h'], 'c': edges.src['c']}

    def reduce_func(self, nodes):
        h_tild = th.sum(nodes.mailbox['h'], 1)
        f = th.sigmoid(self.U_f(nodes.mailbox['h']))
        c = th.sum(f * nodes.mailbox['c'], 1)
        return {'iou': self.U_iou(h_tild), 'c': c}

    def apply_node_func(self, nodes):
        iou = nodes.data['iou'] + self.b_iou
        i, o, u = th.chunk(iou, 3, 1)
        i, o, u = th.sigmoid(i), th.sigmoid(o), th.tanh(u)
        c = i * u + nodes.data['c']
        h = o * th.tanh(c)
        return {'h': h, 'c': c}

class TreeLSTMCell(nn.Module):
    def __init__(self, x_size, h_size):
        super(TreeLSTMCell, self).__init__()
        self.W_iou = nn.Linear(x_size, 3 * h_size, bias=False)
        self.U_iou = nn.Linear(2 * h_size, 3 * h_size, bias=False)
        self.b_iou = nn.Parameter(th.zeros(1, 3 * h_size))
        self.U_f = nn.Linear(2 * h_size, 2 * h_size)

    def message_func(self, edges):
        return {'h': edges.src['h'], 'c': edges.src['c']}

    def reduce_func(self, nodes):
        h_cat = nodes.mailbox['h'].view(nodes.mailbox['h'].size(0), -1)
        f = th.sigmoid(self.U_f(h_cat)).view(*nodes.mailbox['h'].size())
        c = th.sum(f * nodes.mailbox['c'], 1)
        return {'iou': self.U_iou(h_cat), 'c': c}

    def apply_node_func(self, nodes):
        iou = nodes.data['iou'] + self.b_iou
        i, o, u = th.chunk(iou, 3, 1)
        i, o, u = th.sigmoid(i), th.sigmoid(o), th.tanh(u)
        c = i * u + nodes.data['c']
        h = o * th.tanh(c)
        return {'h' : h, 'c' : c}

import dgl.function as fn
import torch as th
import dgl_utils as dglu

class TreeLSTM(nn.Module):
    def __init__(
        self,
        #num_vocabs,
        dataset_num_node_features,
        dataset_num_classes,
        #h_size,
        n_hidden_channels=64,
        dropout=0.5,
        cell_type = "nary",
        global_pool_type = "mean"
        ):
        
        super(TreeLSTM, self).__init__()
        #self.x_size = x_size
        #self.embedding = nn.Embedding(num_vocabs, x_size)
#         if pretrained_emb is not None:
#             print('Using glove')
#             self.embedding.weight.data.copy_(pretrained_emb)
#             self.embedding.weight.requires_grad = True
        self.dropout = nn.Dropout(dropout)
        self.linear = nn.Linear(
            n_hidden_channels, 
            dataset_num_classes)
        
        cell = TreeLSTMCell if cell_type == 'nary' else ChildSumTreeLSTMCell
        self.cell = cell(
            dataset_num_node_features,
            n_hidden_channels)
        
        if global_pool_type is not None:
            self.global_pool_func = eval(f"global_{global_pool_type}_pool")
        else:
            self.global_pool_func = None
            

    def encode(
        self,
        batch,
        h,
        c,
        embeddings):
        
        """Compute tree-lstm prediction given a batch.

        Parameters
        ----------
        batch : dgl.data.SSTBatch
            The data batch.
        h : Tensor
            Initial hidden state.
        c : Tensor
            Initial cell state.

        Returns
        -------
        logits : Tensor
            The prediction of each node.
        """
        # to heterogenous graph
        g = dglu.g_from_data(batch)
        
        #print(f"g = {g}")
        
#         print(f"g.edges = {g.edges()}")
#         print(f"list(dgl.topological_nodes_generator(g)) = {list(dgl.topological_nodes_generator(g))}")
        # feed embedding
        #embeds = self.embedding(batch.wordid * batch.mask)
        embeddings = embeddings# * batch.mask
        g.ndata['iou'] = self.cell.W_iou(
            self.dropout(embeddings),
            #embeddings
        )#* batch.mask.float().unsqueeze(-1)
        g.ndata['h'] = h
        g.ndata['c'] = c
        # propagate
        dgl.prop_nodes_topo(g,
                            message_func=self.cell.message_func,
                            reduce_func=self.cell.reduce_func,
                            apply_node_func=self.cell.apply_node_func)
        # compute logits
        h = self.dropout(g.ndata.pop('h'))
        if self.global_pool_func is not None:
            h = self.global_pool_func(h, batch.batch)
        return h
        
    def forward(
        self,
        batch,
        h,
        c,
        embeddings):
        
        h = self.encode(
        batch=batch,
        h=h,
        c=c,
        embeddings=embeddings)
        
        logits = self.linear(h)
        return F.softmax(logits, dim=-1)
    
# ------------- Models that did not work ------------
"""
import geometric_models as gm
sys.path.append("/pytorch_tools/pytorch_tools/HGP_SL")
import models

model_name = "HGP_SL"
n_epochs = 500


architecture_kwargs = dict(
    n_hidden_channels = 8, 
    #first_heads=8, 
    #output_heads=1, 
    #dropout=0.6,
    #global_pool_type="mean"
)

model = models.Model(
    dataset_num_node_features=dataset.num_node_features,
    dataset_num_classes=dataset.num_classes,
    **architecture_kwargs
    )

"""

'''
GraphSAGE did not import: 

from torch_geometric.nn import SAGEConv
"""
Source: https://colab.research.google.com/github/sachinsharma9780/interactive_tutorials/blob/master/notebooks/example_output/Comprehensive_GraphSage_Guide_with_PyTorchGeometric_Output.ipynb#scrollTo=ROXBserO_amj


How GraphSAGE is different: 

The GraphSage is different from GCNs is two ways: i.e.
1) Instead of taking the entire K-hop neighborhood of a 
    target node, GraphSage first samples or prune the K-hop
    neighborhood computation graph and then perform the 
    feature aggregation operation on this sampled graph 
    in order to generate the embeddings for a target node. 
2) During the learning process, in order to generate the node
    embeddings; GraphSage learns the aggregator function 
    whereas GCNs make use of the symmetrically normalized 
    graph Laplacian.

"""
class SAGE(torch.nn.Module):
    def __init__(
        self, 
        dataset_num_node_features,
        n_hidden_channels, 
        dataset_num_classes,
        n_layers=3):
        super(SAGE, self).__init__()

        self.num_layers = n_layers

        self.convs = torch.nn.ModuleList()
        self.convs.append(SAGEConv(dataset_num_node_features, n_hidden_channels))
        for _ in range(n_layers - 2):
            self.convs.append(SAGEConv(n_hidden_channels, n_hidden_channels))
        self.convs.append(SAGEConv(n_hidden_channels, dataset_num_classes))

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

'''