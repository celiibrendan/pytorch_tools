import torch
import torch.nn as nn
from torch.nn import init
import torch.nn.functional as F
import numpy as np

from modules import Discriminator


# GAT basic operation
class GAT(nn.Module):
    def __init__(self, input_dim, output_dim, add_self=False, normalize_embedding=False,
            dropout=0.0, bias=True):
        super(GAT, self).__init__()

        self.dropout = dropout
        if dropout > 0.001:
            self.dropout_layer = nn.Dropout(p=dropout)

        self.alpha = 0.2
        self.in_features = input_dim
        self.out_features = output_dim
        self.W = nn.Parameter(nn.init.xavier_normal_(torch.Tensor(self.in_features,self.out_features).type(
            torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor), 
            gain=np.sqrt(2.0)), requires_grad=True)
        self.a1 = nn.Parameter(nn.init.xavier_normal_(torch.Tensor(self.out_features, 1).type(
            torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor),
            gain=np.sqrt(2.0)), requires_grad=True)
        self.a2 = nn.Parameter(nn.init.xavier_normal_(torch.Tensor(self.out_features, 1).type(
            torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor),
            gain=np.sqrt(2.0)), requires_grad=True)
        self.leakyrelu = nn.LeakyReLU(self.alpha)
        self.concat = True
  
    def forward(self, x, adj):

        ''' Perform forward prop with graph convolution.
        Returns:
            Embedding matrix with dimension [batch_size x num_nodes x embedding]
        '''
        N, L, D = x.size()
        
        #print(x.shape)
        
        #print(adj.shape)        

        h = torch.mm(x.view(-1, D), self.W).view(N, L, -1)        
        f_1 = torch.matmul(h, self.a1)
        f_2 = torch.matmul(h, self.a2)
        e = self.leakyrelu(f_1 + f_2.transpose(1,2))  
        zero_vec = -9e15*torch.ones_like(e)
        attention = torch.where(adj > 0, e, zero_vec)
        attention = F.softmax(attention, dim=2)
        #attention = F.dropout(attention, self.dropout, training=self.training)
        h_prime = torch.matmul(attention, h)
        
        if self.concat:
            return F.elu(h_prime)
        else:
            return h_prime        

        #print(h.shape)
        #exit()        
        
        return h_prime    

    
class GCN(nn.Module):
    def __init__(self, input_dim, output_dim, add_self=False, normalize_embedding=False,
            dropout=0.0, bias=True):
        super(GCN, self).__init__()
        self.fc = nn.Linear(input_dim, output_dim, bias=False)
        self.act = nn.PReLU()
        
        if bias:
            self.bias = nn.Parameter(torch.FloatTensor(output_dim))
            self.bias.data.fill_(0.0)
        else:
            self.register_parameter('bias', None)

        for m in self.modules():
            self.weights_init(m)

    def weights_init(self, m):
        if isinstance(m, nn.Linear):
            torch.nn.init.xavier_uniform_(m.weight.data)
            if m.bias is not None:
                m.bias.data.fill_(0.0)

    # Shape of seq: (batch, nodes, features)
    def forward(self, seq, adj, sparse=False):
        seq_fts = self.fc(seq)
        if sparse:
            out = torch.unsqueeze(torch.spmm(adj, torch.squeeze(seq_fts, 0)), 0)
        else:
            out = torch.bmm(adj, seq_fts)
        if self.bias is not None:
            out += self.bias
        
        return self.act(out)
    
    

# GCN basic operation
class GraphConv(nn.Module):
    def __init__(self, input_dim, output_dim, add_self=False, normalize_embedding=False,
            dropout=0.0, bias=True):
        super(GraphConv, self).__init__()
        self.add_self = add_self
        self.dropout = dropout
        if dropout > 0.001:
            self.dropout_layer = nn.Dropout(p=dropout)
        self.normalize_embedding = normalize_embedding
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.weight = nn.Parameter(torch.FloatTensor(input_dim, output_dim))#.cuda()
        if bias:
            self.bias = nn.Parameter(torch.FloatTensor(output_dim))#.cuda()
        else:
            self.bias = None
            
            
        self.alpha = 0.2
        self.in_features = input_dim
        self.out_features = output_dim
        self.W = nn.Parameter(nn.init.xavier_normal_(torch.Tensor(self.in_features,self.out_features).type(
            torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor), 
            gain=np.sqrt(2.0)), requires_grad=True)
        self.a1 = nn.Parameter(nn.init.xavier_normal_(torch.Tensor(self.out_features, 1).type(
            torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor),
            gain=np.sqrt(2.0)), requires_grad=True)
        self.a2 = nn.Parameter(nn.init.xavier_normal_(torch.Tensor(self.out_features, 1).type(
            torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor),
            gain=np.sqrt(2.0)), requires_grad=True)
        self.leakyrelu = nn.LeakyReLU(self.alpha)
        self.concat = True
        
        
        
    def _forward(self, x, adj):

        ''' Perform forward prop with graph convolution.
        Returns:
            Embedding matrix with dimension [batch_size x num_nodes x embedding]
        '''
        N, L, D = x.size()
        
        #print(x.shape)
        
        #print(adj.shape)        

        h = torch.mm(x.view(-1, D), self.W).view(N, L, -1)        
        f_1 = torch.matmul(h, self.a1)
        f_2 = torch.matmul(h, self.a2)
        e = self.leakyrelu(f_1 + f_2.transpose(1,2))  
        zero_vec = -9e15*torch.ones_like(e)
        attention = torch.where(adj > 0, e, zero_vec)
        attention = F.softmax(attention, dim=2)
        #attention = F.dropout(attention, self.dropout, training=self.training)
        h_prime = torch.matmul(attention, h)
        
        if self.concat:
            return F.elu(h_prime)
        else:
            return h_prime        

        #print(h.shape)
        #exit()        
        
        return h_prime        
        
        
        
        

    def forward(self, x, adj):
        
        if self.dropout > 0.001:
            x = self.dropout_layer(x)
        
        
        #print(adj.shape)
        #print(x.shape)
            
        #x = torch.squeeze(x, 0)        
        #y = torch.sparse.mm(adj, x)
        #y = y.unsqueeze(0)
        
        
            
        y = torch.matmul(adj, x)
        
        #print(y.shape)
        
        if self.add_self:
            y += x
            
        y = torch.matmul(y, self.weight)
        if self.bias is not None:
            y = y + self.bias
                        
        if self.normalize_embedding:
            y = F.normalize(y, p=2, dim=2)

        return y
    

class _GraphConv(nn.Module):
    def __init__(self, input_dim, output_dim, add_self=False, normalize_embedding=False,
            dropout=0.0, bias=True):
        super(GraphConv, self).__init__()
        self.add_self = add_self
        self.dropout = dropout
        if dropout > 0.001:
            self.dropout_layer = nn.Dropout(p=dropout)
        self.normalize_embedding = normalize_embedding
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.weight = nn.Parameter(torch.FloatTensor(input_dim, output_dim))#.cuda()
        if bias:
            self.bias = nn.Parameter(torch.FloatTensor(output_dim))#.cuda()
        else:
            self.bias = None

    def forward(self, x, adj):
        if self.dropout > 0.001:
            x = self.dropout_layer(x)
        y = torch.matmul(adj, x)
        if self.add_self:
            y += x
        y = torch.matmul(y,self.weight)
        if self.bias is not None:
            y = y + self.bias
        if self.normalize_embedding:
            y = F.normalize(y, p=2, dim=2)
            #print(y[0][0])
        return y    
    
    
    

class GcnEncoderGraph(nn.Module):
    def __init__(self, conv_layers, input_dim, hidden_dim, embedding_dim, label_dim, num_layers,
            pred_hidden_dims=[], concat=True, bn=True, dropout=0.0, args=None):
        super(GcnEncoderGraph, self).__init__()
        self.concat = concat
        add_self = not concat
        self.bn = bn
        self.num_layers = num_layers
        self.num_aggs=1        
        
        self.sigm = nn.Sigmoid()
        self.disc = Discriminator(hidden_dim*3)
        self.b_xent = nn.BCEWithLogitsLoss(reduce=False)
        self.xent = nn.CrossEntropyLoss()

        self.bias = True
        if args is not None:
            self.bias = args.bias

        self.conv_first, self.conv_block, self.conv_last = self.build_conv_layers(
                conv_layers, input_dim, hidden_dim, embedding_dim, num_layers, 
                add_self, normalize=True, dropout=dropout)
        self.act = nn.ReLU()
        self.label_dim = label_dim

        if concat:
            self.pred_input_dim = hidden_dim * (num_layers - 1) + embedding_dim
        else:
            self.pred_input_dim = embedding_dim
        self.pred_model = self.build_pred_layers(self.pred_input_dim, pred_hidden_dims, 
                label_dim, num_aggs=self.num_aggs)

        for m in self.modules():
            if isinstance(m, GraphConv):
                m.weight.data = init.xavier_uniform_(m.weight.data, gain=nn.init.calculate_gain('relu'))
                if m.bias is not None:
                    m.bias.data = init.constant_(m.bias.data, 0.0)
                    

    def build_conv_layers(self, conv_layers, input_dim, hidden_dim, embedding_dim, num_layers, 
            add_self, normalize=False, dropout=0.0):
        if conv_layers == 'GAT':
            conv_first = GAT(input_dim=input_dim, output_dim=hidden_dim, add_self=add_self,
                    normalize_embedding=normalize, bias=self.bias)
        else:
            conv_first = GCN(input_dim=input_dim, output_dim=hidden_dim, add_self=add_self,
                    normalize_embedding=normalize, bias=self.bias)            
        conv_block = nn.ModuleList(
                [GCN(input_dim=hidden_dim, output_dim=hidden_dim, add_self=add_self,
                        normalize_embedding=normalize, dropout=dropout, bias=self.bias) 
                 for i in range(num_layers-2)])
        conv_last = GCN(input_dim=hidden_dim, output_dim=embedding_dim, add_self=add_self,
                normalize_embedding=normalize, bias=self.bias)
        return conv_first, conv_block, conv_last

    def build_pred_layers(self, pred_input_dim, pred_hidden_dims, label_dim, num_aggs=1):
        pred_input_dim = pred_input_dim * num_aggs
        if len(pred_hidden_dims) == 0:
            pred_model = nn.Linear(pred_input_dim, label_dim)
        else:
            pred_layers = []
            for pred_dim in pred_hidden_dims:
                pred_layers.append(nn.Linear(pred_input_dim, pred_dim))
                pred_layers.append(self.act)
                pred_input_dim = pred_dim
            pred_layers.append(nn.Linear(pred_dim, label_dim))
            pred_model = nn.Sequential(*pred_layers)
        return pred_model

    def construct_mask(self, max_nodes, batch_num_nodes): 
        ''' For each num_nodes in batch_num_nodes, the first num_nodes entries of the 
        corresponding column are 1's, and the rest are 0's (to be masked out).
        Dimension of mask: [batch_size x max_nodes x 1]
        '''
        # masks
        packed_masks = [torch.ones(int(num)) for num in batch_num_nodes]
        batch_size = len(batch_num_nodes)
        out_tensor = torch.zeros(batch_size, max_nodes)
        for i, mask in enumerate(packed_masks):
            out_tensor[i, :batch_num_nodes[i]] = mask
        return out_tensor.unsqueeze(2)#.cuda()
    
    def apply_bn(self, x):
        ''' Batch normalization of 3D tensor x
        '''
        bn_module = nn.BatchNorm1d(x.size()[1])#.cuda()
        return bn_module(x)

    
    def gcn_forward(self, x, adj, conv_first, conv_block, conv_last, embedding_mask=None):

        ''' Perform forward prop with graph convolution.
        Returns:
            Embedding matrix with dimension [batch_size x num_nodes x embedding]
        '''
        x = conv_first(x, adj)
        x = self.act(x)
        if self.bn:
            x = self.apply_bn(x)
        x_all = [x]
        #out_all = []
        #out, _ = torch.max(x, dim=1)
        #out_all.append(out)
        for i in range(len(conv_block)):
            x = conv_block[i](x,adj)
            x = self.act(x)
            if self.bn:
                x = self.apply_bn(x)
            x_all.append(x)
        x = conv_last(x,adj)
        x_all.append(x)
        # x_tensor: [batch_size x num_nodes x embedding]
        x_tensor = torch.cat(x_all, dim=2)
        if embedding_mask is not None:
            x_tensor = x_tensor * embedding_mask
        
        return x_tensor

    def forward(self, x, adj, batch_num_nodes=None, **kwargs):
        # mask
        max_num_nodes = adj.size()[1]
        if batch_num_nodes is not None:
            self.embedding_mask = self.construct_mask(max_num_nodes, batch_num_nodes)
        else:
            self.embedding_mask = None

        # conv
        x = self.conv_first(x, adj)
        x = self.act(x)
        if self.bn:
            x = self.apply_bn(x)
        out_all = []
        out, _ = torch.max(x, dim=1)

        out_all.append(out)
        for i in range(self.num_layers-2):
            x = self.conv_block[i](x,adj)
            x = self.act(x)
            if self.bn:
                x = self.apply_bn(x)
            out,_ = torch.max(x, dim=1)
            out_all.append(out)
            if self.num_aggs == 2:
                out = torch.sum(x, dim=1)
                out_all.append(out)
        x = self.conv_last(x,adj)
        #x = self.act(x)
        out, _ = torch.max(x, dim=1)
        out_all.append(out)
        if self.num_aggs == 2:
            out = torch.sum(x, dim=1)
            out_all.append(out)
        if self.concat:
            output = torch.cat(out_all, dim=1)
        else:
            output = out          
            
        ypred = self.pred_model(output)
        #print(output.size())
        return ypred

    def loss(self, pred, label, type='softmax'):
        # softmax + CE
        if type == 'softmax':
            return F.cross_entropy(pred, label, size_average=True)
        elif type == 'margin':
            batch_size = pred.size()[0]
            label_onehot = torch.zeros(batch_size, self.label_dim).long()#.cuda()
            label_onehot.scatter_(1, label.view(-1,1), 1)
            return torch.nn.MultiLabelMarginLoss()(pred, label_onehot)
            
        #return F.binary_cross_entropy(F.sigmoid(pred[:,0]), label.float())


class SoftPoolingGcnEncoder(GcnEncoderGraph):
    def __init__(self, conv_layers, max_num_nodes, input_dim, hidden_dim, embedding_dim, label_dim, num_layers,
            assign_hidden_dim, assign_ratio=0.25, assign_num_layers=-1, num_pooling=1,
            pred_hidden_dims=[50], concat=True, bn=True, dropout=0.0, linkpred=True,
            assign_input_dim=-1, args=None):
        '''
        Args:
            num_layers: number of gc layers before each pooling
            num_nodes: number of nodes for each graph in batch
            linkpred: flag to turn on link prediction side objective
        '''

        super(SoftPoolingGcnEncoder, self).__init__(conv_layers, input_dim, hidden_dim, embedding_dim, label_dim,
                num_layers, pred_hidden_dims=pred_hidden_dims, concat=concat, args=args)
        add_self = not concat
        self.num_pooling = num_pooling
        self.linkpred = linkpred
        self.assign_ent = True

        # GC
        self.conv_first_after_pool = []
        self.conv_block_after_pool = []
        self.conv_last_after_pool = []
        for i in range(num_pooling):
            # use self to register the modules in self.modules()
            self.conv_first2, self.conv_block2, self.conv_last2 = self.build_conv_layers(
                    conv_layers, self.pred_input_dim, hidden_dim, embedding_dim, num_layers, 
                    add_self, normalize=True, dropout=dropout)
            self.conv_first_after_pool.append(self.conv_first2)
            self.conv_block_after_pool.append(self.conv_block2)
            self.conv_last_after_pool.append(self.conv_last2)

        # assignment
        assign_dims = []
        if assign_num_layers == -1:
            assign_num_layers = num_layers
        if assign_input_dim == -1:
            assign_input_dim = input_dim

        self.assign_conv_first_modules = []
        self.assign_conv_block_modules = []
        self.assign_conv_last_modules = []
        self.assign_pred_modules = []
        assign_dim = int(max_num_nodes * assign_ratio)
        for i in range(num_pooling):
            assign_dims.append(assign_dim)
            self.assign_conv_first, self.assign_conv_block, self.assign_conv_last = self.build_conv_layers(
                    conv_layers, assign_input_dim, assign_hidden_dim, assign_dim, assign_num_layers, add_self,
                    normalize=True)
            assign_pred_input_dim = assign_hidden_dim * (num_layers - 1) + assign_dim if concat else assign_dim
            self.assign_pred = self.build_pred_layers(assign_pred_input_dim, [], assign_dim, num_aggs=1)


            # next pooling layer
            assign_input_dim = embedding_dim
            assign_dim = int(assign_dim * assign_ratio)

            self.assign_conv_first_modules.append(self.assign_conv_first)
            self.assign_conv_block_modules.append(self.assign_conv_block)
            self.assign_conv_last_modules.append(self.assign_conv_last)
            self.assign_pred_modules.append(self.assign_pred)

        self.pred_model = self.build_pred_layers(self.pred_input_dim * (num_pooling+1), pred_hidden_dims, 
                label_dim, num_aggs=self.num_aggs)

        for m in self.modules():
            if isinstance(m, GraphConv):
                m.weight.data = init.xavier_uniform_(m.weight.data, gain=nn.init.calculate_gain('relu'))
                if m.bias is not None:
                    m.bias.data = init.constant_(m.bias.data, 0.0)

    def readout(self, x, adj, shuf_fts, batch_num_nodes, x_a):

        # mask
        max_num_nodes = adj.size()[1]
        if batch_num_nodes is not None:
            embedding_mask = self.construct_mask(max_num_nodes, batch_num_nodes)
        else:
            embedding_mask = None

        out_all = []

        #self.assign_tensor = self.gcn_forward(x_a, adj, 
        #        self.assign_conv_first_modules[0], self.assign_conv_block_modules[0], self.assign_conv_last_modules[0],
        #        embedding_mask)
        ## [batch_size x num_nodes x next_lvl_num_nodes]
        #self.assign_tensor = nn.Softmax(dim=-1)(self.assign_pred(self.assign_tensor))
        #if embedding_mask is not None:
        #    self.assign_tensor = self.assign_tensor * embedding_mask
        
        
        # [batch_size x num_nodes x embedding_dim]
        embedding_tensor = self.gcn_forward(x, adj,
                self.conv_first, self.conv_block, self.conv_last, embedding_mask)
        
        shuf_embedding_tensor = self.gcn_forward(shuf_fts, adj,
                self.conv_first, self.conv_block, self.conv_last, embedding_mask)        
        
        
        
        origin_embedding_tensor = embedding_tensor
        origin_embedding_mask = embedding_mask
        
        out, _ = torch.max(embedding_tensor, dim=1)
        out_all.append(out)
        if self.num_aggs == 2:
            out = torch.sum(embedding_tensor, dim=1)
            out_all.append(out)

        for i in range(self.num_pooling):
            if batch_num_nodes is not None and i == 0:
                embedding_mask = self.construct_mask(max_num_nodes, batch_num_nodes)
            else:
                embedding_mask = None

            self.assign_tensor = self.gcn_forward(x_a, adj, 
                    self.assign_conv_first_modules[i], self.assign_conv_block_modules[i], self.assign_conv_last_modules[i],
                    embedding_mask)
            # [batch_size x num_nodes x next_lvl_num_nodes]
            self.assign_tensor = nn.Softmax(dim=-1)(self.assign_pred(self.assign_tensor))
            if embedding_mask is not None:
                self.assign_tensor = self.assign_tensor * embedding_mask

            # update pooled features and adj matrix
            x = torch.matmul(torch.transpose(self.assign_tensor, 1, 2), embedding_tensor)
            adj = torch.transpose(self.assign_tensor, 1, 2) @ adj @ self.assign_tensor
            x_a = x
        
            embedding_tensor = self.gcn_forward(x, adj, 
                    self.conv_first_after_pool[i], self.conv_block_after_pool[i],
                    self.conv_last_after_pool[i])


            out, _ = torch.max(embedding_tensor, dim=1)
            out_all.append(out)
            if self.num_aggs == 2:
                #out = torch.mean(embedding_tensor, dim=1)
                out = torch.sum(embedding_tensor, dim=1)
                out_all.append(out)


        if self.concat:
            output = torch.cat(out_all, dim=1)
        else:
            output = out 
            
        
        #output = torch.mean(origin_embedding_tensor, 1)
            
        return output, origin_embedding_tensor, shuf_embedding_tensor, origin_embedding_mask
    
    def forward(self, x, adj, shuf_fts, batch_num_nodes, **kwargs):
        if 'assign_x' in kwargs:
            x_a = kwargs['assign_x']
        else:
            x_a = x

        c, origin_embedding_tensor, shuf_embedding_tensor, _ = self.readout(x, adj, shuf_fts, batch_num_nodes, x_a)
        
        c = self.sigm(c)
        
        
        logits = self.disc(c, origin_embedding_tensor, shuf_embedding_tensor)
        
        batch_size = adj.size()[0]
        
        max_num_nodes = adj.size()[1]
        
        lbl_1 = torch.ones(batch_size, max_num_nodes)
        
        lbl_2 = torch.zeros(batch_size, max_num_nodes)
        
        lbl = torch.cat((lbl_1, lbl_2), 1)
        
        if torch.cuda.is_available():
            lbl = lbl#.cuda()
        
        #print(c.shape)
        #print(origin_embedding_tensor.shape)
        #print(shuf_embedding_tensor.shape)
        
        #print(logits.shape)
        #print(lbl.shape)

        all_loss_output = self.b_xent(logits, lbl)
        
        loss = self.compute_loss(all_loss_output, batch_num_nodes, max_num_nodes)
        
        
        if self.linkpred:
            max_num_nodes = adj.size()[1]
            pred_adj0 = self.assign_tensor @ torch.transpose(self.assign_tensor, 1, 2) 
            tmp = pred_adj0
            pred_adj = pred_adj0
            for adj_pow in range(adj_hop-1):
                tmp = tmp @ pred_adj0
                pred_adj = pred_adj + tmp
            pred_adj = torch.min(pred_adj, torch.Tensor(1))#.cuda()
            #print('adj1', torch.sum(pred_adj0) / torch.numel(pred_adj0))
            #print('adj2', torch.sum(pred_adj) / torch.numel(pred_adj))
            #self.link_loss = F.nll_loss(torch.log(pred_adj), adj)
            self.link_loss = -adj * torch.log(pred_adj+eps) - (1-adj) * torch.log(1-pred_adj+eps)
            if batch_num_nodes is None:
                num_entries = max_num_nodes * max_num_nodes * adj.size()[0]
                print('Warning: calculating link pred loss without masking')
            else:
                num_entries = np.sum(batch_num_nodes * batch_num_nodes)
                embedding_mask = self.construct_mask(max_num_nodes, batch_num_nodes)
                adj_mask = embedding_mask @ torch.transpose(embedding_mask, 1, 2)
                self.link_loss[1-adj_mask.byte()] = 0.0

            self.link_loss = torch.sum(self.link_loss) / float(num_entries)
            #print('linkloss: ', self.link_loss)
            return loss #+ self.link_loss
        
        return loss
        
        #print(loss)
        
        #exit()
        
        #ypred = self.pred_model(output)
        
        #return ypred 
        
    def embed(self, x, adj, shuf_fts, batch_num_nodes, **kwargs):
        if 'assign_x' in kwargs:
            x_a = kwargs['assign_x']
        else:
            x_a = x

        c, origin_embedding_tensor, shuf_embedding_tensor, _ = self.readout(x, adj, shuf_fts, batch_num_nodes, x_a)
        
        return origin_embedding_tensor.detach(), c.detach()
    
    
    def compute_loss(self, all_loss_output, batch_num_nodes, max_num_nodes):
        
        loss = torch.zeros(1) 
        total = torch.FloatTensor([np.sum(batch_num_nodes)])
        if torch.cuda.is_available():
            loss = loss#.cuda()
            total = total#.cuda()
        
        for loss_output, num_nodes in zip(all_loss_output, batch_num_nodes):
            loss += torch.sum(loss_output[:num_nodes])
            loss += torch.sum(loss_output[max_num_nodes:max_num_nodes+num_nodes])

        return loss/total
    

    def loss(self, pred, label, adj=None, batch_num_nodes=None, adj_hop=1):
        ''' 
        Args:
            batch_num_nodes: numpy array of number of nodes in each graph in the minibatch.
        '''
        eps = 1e-7
        loss = super(SoftPoolingGcnEncoder, self).loss(pred, label)
        if self.linkpred:
            max_num_nodes = adj.size()[1]
            pred_adj0 = self.assign_tensor @ torch.transpose(self.assign_tensor, 1, 2) 
            tmp = pred_adj0
            pred_adj = pred_adj0
            for adj_pow in range(adj_hop-1):
                tmp = tmp @ pred_adj0
                pred_adj = pred_adj + tmp
            pred_adj = torch.min(pred_adj, torch.Tensor(1))#.cuda()
            #print('adj1', torch.sum(pred_adj0) / torch.numel(pred_adj0))
            #print('adj2', torch.sum(pred_adj) / torch.numel(pred_adj))
            #self.link_loss = F.nll_loss(torch.log(pred_adj), adj)
            self.link_loss = -adj * torch.log(pred_adj+eps) - (1-adj) * torch.log(1-pred_adj+eps)
            if batch_num_nodes is None:
                num_entries = max_num_nodes * max_num_nodes * adj.size()[0]
                print('Warning: calculating link pred loss without masking')
            else:
                num_entries = np.sum(batch_num_nodes * batch_num_nodes)
                embedding_mask = self.construct_mask(max_num_nodes, batch_num_nodes)
                adj_mask = embedding_mask @ torch.transpose(embedding_mask, 1, 2)
                self.link_loss[1-adj_mask.byte()] = 0.0

            self.link_loss = torch.sum(self.link_loss) / float(num_entries)
            #print('linkloss: ', self.link_loss)
            return loss + self.link_loss
        return loss

