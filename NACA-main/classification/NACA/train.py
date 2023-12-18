# -*- coding: utf-8 -*-
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data
import models
from tqdm import tqdm


def train(args, device, train_loader, traintest_loader, test_loader):
    for trial in range(1, args.trials + 1):
        # Network topology
        model = models.NetworkBuilder(args.topology, input_size=args.input_size, input_channels=args.input_channels, label_features=args.label_features, train_batch_size=args.batch_size, dropout=args.dropout, fc_zero_init=args.fc_zero_init, spike_window=args.spike_window, device=device, thresh=args.thresh, randKill=args.randKill, lens=args.lens, decay=args.decay, conv_act=args.conv_act, hidden_act=args.hidden_act, output_act=args.output_act)

        if args.cuda:
            model.to(device)
        if args.optimizer == 'SGD':
            optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, nesterov=False)
        elif args.optimizer == 'NAG':
            optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, nesterov=True)
        elif args.optimizer == 'Adam':
            optimizer = optim.Adam(model.parameters(), lr=args.lr)
        elif args.optimizer == 'RMSprop':
            optimizer = optim.RMSprop(model.parameters(), lr=args.lr)
        else:
            raise NameError("=== ERROR: optimizer " + str(args.optimizer) + " not supported")

        # Loss function
        if args.loss == 'MSE':
            loss = (F.mse_loss, (lambda l: l))
        elif args.loss == 'BCE':
            loss = (F.binary_cross_entropy, (lambda l: l))
        elif args.loss == 'CE':
            loss = (F.cross_entropy, (lambda l: torch.max(l, 1)[1]))
        else:
            raise NameError("=== ERROR: loss " + str(args.loss) + " not supported")

        print("\n\n=== Starting model training with %d epochs:\n" % (args.epochs))
        for epoch in range(1, args.epochs + 1):
            train_epoch(args, model, device, train_loader, optimizer, loss)

            print("\nSummary of epoch %d:" % (epoch))
            test_epoch(args, model, device, traintest_loader, loss, 'Train', epoch)
            test_epoch(args, model, device, test_loader, loss, 'Test', epoch)


def train_epoch(args, model, device, train_loader, optimizer, loss):
    model.train()

    for batch_idx, (data, label) in enumerate(tqdm(train_loader)):
        if args.quickexit:
            if batch_idx > 23:
                break
        data, label = data.to(device), label.to(device)
        if args.regression:
            targets = label
        else:
            targets = torch.zeros(label.shape[0], args.label_features, device=device).scatter_(1, label.unsqueeze(1).long(), 1.0)

        optimizer.zero_grad()
        output = model(data, targets)
        loss_val = loss[0](output, loss[1](targets))
        loss_val.backward(retain_graph=False)
        optimizer.step()


def test_epoch(args, model, device, test_loader, loss, phase, epoch):
    model.eval()

    test_loss, correct = 0, 0
    counter = 0
    with torch.no_grad():
        for data, label in test_loader:
            if args.quickexit:
                if counter > 23:
                    break
            data, label = data.to(device), label.to(device)
            if args.regression:
                targets = label
            else:
                targets = torch.zeros(label.shape[0], args.label_features, device=device).scatter_(1, label.unsqueeze(1).long(), 1.0)

            output = model(data, None)

            test_loss += loss[0](output, loss[1](targets), reduction='sum').item()
            pred = output.max(1, keepdim=True)[1]
            if not args.regression:
                correct += pred.eq(label.view_as(pred).long()).sum().item()
            counter += 1

    loss = test_loss / (counter * args.batch_size)
    if not args.regression:
        acc = 100. * correct / (counter * args.batch_size)
        print("\t[%5sing set] Loss: %6f, Accuracy: %6.2f%%" % (phase, loss, acc))

        filetestloss = writefile(args, '/testloss.txt')
        filetestacc = writefile(args, '/testacc.txt')
        filetrainloss = writefile(args, '/trainloss.txt')
        filetrainacc = writefile(args, '/trainacc.txt')

        if phase == 'Train':
            filetrainloss.write(str(epoch) + ' ' + str(loss) + '\n')
            filetrainacc.write(str(epoch) + ' ' + str(acc) + '\n')
        if phase == 'Test':
            filetestloss.write(str(epoch) + ' ' + str(loss) + '\n')
            filetestacc.write(str(epoch) + ' ' + str(acc) + '\n')
    else:
        print("\t[%5sing set] Loss: %6f" % (phase, loss))


def writefile(args, file):
    filepath = 'output/' + args.codename
    filetestloss = open(filepath + file, 'a')
    return filetestloss