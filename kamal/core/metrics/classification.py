from .stream_metrics import StreamMetricsBase
import numpy as np
import torch

class StreamClassificationMetrics(StreamMetricsBase):
    PRIMARY_METRIC = 'acc'
    def __init__(self):
        self.correct = 0
        self.total = 0

    def update(self, logits, targets):
        preds = logits.max(1)[1]
        if isinstance(preds, torch.Tensor):
            preds = preds.detach().cpu().numpy()
            targets = targets.detach().cpu().numpy()
        self.correct += (preds.flatten()==targets.flatten()).sum()
        self.total += len(targets)

    @staticmethod
    def to_str(results):
        return "%s: %.4f"%( 'Acc', results['acc'] )

    def get_results(self):
        return {"acc": self.correct / self.total }
    
    def reset(self):
        self.correct = self.total = 0


class StreamClassificationTopKMetrics(StreamMetricsBase):
    PRIMARY_METRIC = 'acc@1'
    def __init__(self, topk=(1, )):
        self.topk_correct = { k:0 for k in topk }
        self.total = 0
        self._max_k = max(topk)
        self._topk = topk
        
    def update(self, logits, targets):
        _, preds = logits.topk(self._max_k, dim=1, largest=True, sorted=True)
        correct = preds.eq( targets.view(-1, 1).expand_as(preds) )
        for k in self._topk:
            self.topk_correct[k] += correct[:, :k].view(-1).float().sum(0).item()
        self.total += len(targets)
    
    @staticmethod
    def to_str(results):
        topk_str = ""
        for k, v in results:
            topk_str+="%s: %.4f "%( k, results[k] )
        return topk_str
    
    def get_results(self):
        return { 'acc@%d'%k: self.topk_correct[k] / self.total for k in self._topk }

    def reset(self):
        self.correct = { k:0 for k in self._topk }
        self.total = 0


class StreamCEMAPMetrics():
    PRIMARY_METRIC = 'eap'
    def __init__(self):
        self.targets = None
        self.preds = None

    def update(self, logits, targets):
        preds = logits.max(1)[1]
        # targets: -1 negative, 0 difficult, 1 positive
        if isinstance(preds, torch.Tensor):
            preds = preds.cpu().numpy()
            targets = targets.cpu().numpy()

        self.preds = preds if self.preds is None else np.append(self.preds, preds, axis=0)
        self.targets = targets if self.targets is None else np.append(self.targets, targets, axis=0)

    @staticmethod
    def to_str(results):
        string = "\n"
        for k, v in results.items():
            string += '{}: {}\n'.format(k, v)
        return string

    def get_results(self):
        nTest = self.targets.shape[0]
        nLabel = self.targets.shape[1]
        eap = np.zeros(nTest)
        for i in range(0,nTest):
            R = np.sum(self.targets[i,:]==1)
            for j in range(0,nLabel):            
                if self.targets[i,j]==1:
                    r = np.sum(self.preds[i,np.nonzero(self.targets[i,:]!=0)]>=self.preds[i,j])
                    rb = np.sum(self.preds[i,np.nonzero(self.targets[i,:]==1)] >= self.preds[i,j])

                    eap[i] = eap[i] + rb/(r*1.0)
            eap[i] = eap[i]/R
        # emap = np.nanmean(ap)

        cap = np.zeros(nLabel)
        for i in range(0,nLabel):
            R = np.sum(self.targets[:,i]==1)
            for j in range(0,nTest):
                if self.targets[j,i]==1:
                    r = np.sum(self.preds[np.nonzero(self.targets[:,i]!=0),i] >= self.preds[j,i])
                    rb = np.sum(self.preds[np.nonzero(self.targets[:,i]==1),i] >= self.preds[j,i])
                    cap[i] = cap[i] + rb/(r*1.0)
            cap[i] = cap[i]/R
        # cmap = np.nanmean(ap)
        return {
            'eap': eap,
            'emap': np.nanmean(eap),
            'cap': cap,
            'cmap': np.nanmean(cap),
        }

    def reset(self):
        self.preds = None
        self.targets = None
        