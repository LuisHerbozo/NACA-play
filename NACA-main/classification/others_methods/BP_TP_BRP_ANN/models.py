# -*- coding: utf-8 -*-

import torch
import torch.nn as nn
import function
from module import FA_wrapper, TrainingHook
import utils

spike_args = {}


class NetworkBuilder(nn.Module):
    def __init__(self, topology, input_size, input_channels, label_features, train_batch_size, train_mode, dropout,
                 conv_act, hidden_act, output_act, fc_zero_init, spike_window, device, thresh, randKill, lens, decay):
        super(NetworkBuilder, self).__init__()

        self.layers = nn.ModuleList()
        self.batch_size = train_batch_size
        self.spike_window = spike_window
        self.randKill = randKill
        spike_args['thresh'] = thresh
        spike_args['lens'] = lens
        spike_args['decay'] = decay

        if (train_mode == "DFA") or (train_mode == "sDFA"):
            self.y = torch.zeros(train_batch_size, label_features, device=device)
            self.y.requires_grad = False
        else:
            self.y = None

        topology = topology.split('_')
        self.topology = topology
        topology_layers = []
        num_layers = 0
        for elem in topology:
            if not any(i.isdigit() for i in elem):
                num_layers += 1
                topology_layers.append([])
            topology_layers[num_layers - 1].append(elem)
        for i in range(num_layers):
            layer = topology_layers[i]
            try:
                if layer[0] == "CONV":
                    in_channels = input_channels if (i == 0) else out_channels
                    out_channels = int(layer[1])
                    input_dim = input_size if (i == 0) else int(
                        output_dim / 2)
                    output_dim = int((input_dim - int(layer[2]) + 2 * int(layer[4])) / int(layer[3])) + 1
                    self.layers.append(CNN_block(
                        in_channels=in_channels,
                        out_channels=int(layer[1]),
                        kernel_size=int(layer[2]),
                        stride=int(layer[3]),
                        padding=int(layer[4]),
                        bias=True,
                        activation=conv_act,
                        dim_hook=[label_features, out_channels, output_dim, output_dim],
                        label_features=label_features,
                        train_mode=train_mode,
                        batch_size=self.batch_size,
                        spike_window=self.spike_window
                    ))
                elif layer[0] == "FC":
                    if (i == 0):
                        input_dim = pow(input_size,2)*input_channels
                        self.conv_to_fc = 0
                    elif topology_layers[i - 1][0] == "CONV":
                        input_dim = pow(int(output_dim / 2), 2) * int(topology_layers[i - 1][1])
                        self.conv_to_fc = i
                    elif topology_layers[i - 1][0] == "C":
                        input_dim = pow(int(output_dim) ,1) * int(topology_layers[i - 1][2]) *int(int(topology_layers[i - 1][1])/10)
                        self.conv_to_fc = i
                    else:
                        input_dim = output_dim

                    output_dim = int(layer[1])
                    output_layer = (i == (num_layers - 1))
                    self.layers.append(FC_block(
                        in_features=input_dim,
                        out_features=output_dim,
                        bias=True,
                        activation=output_act if output_layer else hidden_act,
                        dropout=dropout,
                        dim_hook=None if output_layer else [label_features, output_dim],
                        label_features=label_features,
                        fc_zero_init=fc_zero_init,
                        train_mode=("BP" if (train_mode != "FA") else "FA") if output_layer else train_mode,
                        batch_size=train_batch_size,
                        spike_window=self.spike_window
                    ))

                elif layer[0] == "C":
                    in_channels = input_channels if (i == 0) else out_channels
                    out_channels = int(layer[1])
                    input_dim = input_size if (i == 0) else int(output_dim / 2)
                    output_dim = int((input_dim + 2*int(layer[4]) - int(layer[2]) + 1) / int(layer[3]))
                    self.layers.append(C_block(
                        in_channels=in_channels,
                        out_channels=int(layer[1]),
                        kernel_size=int(layer[2]),
                        stride=int(layer[3]),
                        padding=int(layer[4]),
                        bias=True,
                        activation=conv_act,
                        dim_hook=[label_features, out_channels, output_dim],
                        label_features=label_features,
                        train_mode=train_mode,
                        batch_size=self.batch_size,
                        spike_window=self.spike_window
                    ))
                else:
                    raise NameError("=== ERROR: layer construct " + str(elem) + " not supported")
            except ValueError as e:
                raise ValueError("=== ERROR: unsupported layer parameter format: " + str(e))

    def forward(self, input, labels):
        x = input.float().cuda() * utils.args.randKill

        for i in range(len(self.layers)):
            if i == self.conv_to_fc:
                x = x.reshape(x.size(0), -1)
            x = self.layers[i](x, labels, self.y)

        if x.requires_grad and (self.y is not None):
            self.y.data.copy_(x.data)

        return x


class ActFun(torch.autograd.Function):

    @staticmethod
    def forward(ctx, input):
        ctx.save_for_backward(input)
        return input.gt(spike_args['thresh']).float()

    @staticmethod
    def backward(ctx, grad_output):
        input, = ctx.saved_tensors
        grad_input = grad_output.clone()
        temp = abs(input - spike_args['thresh']) < spike_args['lens']
        return grad_input * temp.float()

act_fun = ActFun.apply


def mem_update(ops, x, mem, spike, lateral=None):
    mem = mem * spike_args['decay'] * (1. - spike) + ops(x)

    if lateral:
        mem += lateral(spike)
    spike = act_fun(mem)
    return mem, spike


class FC_block(nn.Module):
    def __init__(self, in_features, out_features, bias, activation, dropout, dim_hook, label_features, fc_zero_init,
                 train_mode, batch_size, spike_window):
        super(FC_block, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.batch_size = batch_size
        self.spike_window = spike_window
        self.dropout = dropout
        self.fc = nn.Linear(in_features=in_features, out_features=out_features, bias=bias)
        if fc_zero_init:
            torch.zero_(self.fc.weight.data)
        if train_mode == 'FA':
            self.fc = FA_wrapper(module=self.fc, layer_type='fc', dim=self.fc.weight.shape)
        self.act = Activation(activation)
        if dropout != 0:
            self.drop = nn.Dropout(p=dropout)
        self.hook = TrainingHook(label_features=label_features, dim_hook=dim_hook, train_mode=train_mode)
        self.mem = None
        self.spike = None
        self.sumspike = None
        self.time_counter = 0
        self.out = None

    def forward(self, x, labels, y):
        x = self.fc(x)
        x = self.act(x)
        if self.dropout != 0:
            x = self.drop(x)
        x = self.hook(x, labels, y, self.out)
        return x


class CNN_block(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride, padding, bias, activation, dim_hook,label_features, train_mode, batch_size, spike_window):
        super(CNN_block, self).__init__()
        self.spike_window = spike_window
        self.conv = nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size,
                              stride=stride, padding=padding, bias=bias)
        if train_mode == 'FA':
            self.conv = FA_wrapper(module=self.conv, layer_type='conv', dim=self.conv.weight.shape, stride=stride,
                                   padding=padding)
        self.act = Activation(activation)
        if utils.args.pool == 'Avg':
            self.pool = nn.AvgPool2d(kernel_size=2, stride=2)
        else:
            self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        self.BN = nn.BatchNorm2d(out_channels)
        self.hook = TrainingHook(label_features=label_features, dim_hook=dim_hook, train_mode=train_mode)
        self.mem = None
        self.spike = None
        self.sumspike = None
        self.time_counter = 0
        self.batch_size = batch_size
        self.out_channels = out_channels
        self.out = None

    def forward(self, x, labels, y):
        x = self.conv(x)
        x = self.act(x)
        x = self.hook(x, labels, y, self.out)
        self.out = x.detach()
        x = self.pool(x)

        return x

class C_block(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride, padding, bias, activation, dim_hook,label_features, train_mode, batch_size, spike_window):
        super(C_block, self).__init__()
        self.spike_window = spike_window
        self.conv = nn.Conv1d(in_channels=in_channels, out_channels=out_channels,kernel_size=kernel_size,stride=stride, padding=padding, bias=bias)
        if train_mode == 'FA':
            self.conv = FA_wrapper(module=self.conv, layer_type='conv', dim=self.conv.weight.shape, stride=stride,padding=padding)
        self.act = Activation(activation)
        self.pool = nn.AvgPool1d(kernel_size=kernel_size)
        self.hook = TrainingHook(label_features=label_features, dim_hook=dim_hook, train_mode=train_mode)
        self.mem = None
        self.spike = None
        self.sumspike = None
        self.time_counter = 0
        self.batch_size = batch_size
        self.out_channels = out_channels

    def forward(self, x, labels, y):
        if self.time_counter == 0:
            if x.size()[-2] == 1:
                self.mem = torch.zeros((self.batch_size, self.out_channels, x.size()[-1])).cuda()
                self.spike = torch.zeros((self.batch_size, self.out_channels, x.size()[-1])).cuda()
                self.sumspike = torch.zeros((self.batch_size, self.out_channels, x.size()[-1])).cuda()
            else:
                self.mem = torch.zeros((self.batch_size, self.out_channels, x.size()[-2], x.size()[-1])).cuda()
                self.spike = torch.zeros((self.batch_size, self.out_channels, x.size()[-2], x.size()[-1])).cuda()
                self.sumspike = torch.zeros((self.batch_size, self.out_channels, x.size()[-2], x.size()[-1])).cuda()

        self.time_counter += 1
        self.mem, self.spike = mem_update(self.conv, x, self.mem, self.spike)

        x = self.hook(self.spike, labels, y)

        x = self.pool(x)

        if self.time_counter == self.spike_window:
            self.time_counter = 0

        return x


class Activation(nn.Module):
    def __init__(self, activation):
        super(Activation, self).__init__()

        if activation == "tanh":
            self.act = nn.Tanh()
        elif activation == "sigmoid":
            self.act = nn.Sigmoid()
        elif activation == "relu":
            self.act = nn.ReLU()
        elif activation == "none":
            self.act = None
        else:
            raise NameError("=== ERROR: activation " + str(activation) + " not supported")

    def forward(self, x):
        if self.act == None:
            return x
        else:
            return self.act(x)
