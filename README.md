# NACA

Synaptic connections in the brain are known to be locally modulated by neural activity via many forms of synaptic plasticity, 
including long-term synaptic potentiation and depression associated with spike timing-dependent plasticity1 (STDP). 
Neuromodulators in the brain also act globally at many synapses to modify the capacity and property of local STDP2, 
and such metaplasticity is rarely considered by existing artificial neural networks.
Here we report a new brain-inspired computing algorithm for the spiking neural networks (SNNs) and non-spiking artificial neural networks (ANNs)
that incorporates metaplastic changes previously observed in the brain, via neuromodulation of the STDP form at selective synapses. 
Referred here as Neuromodulation-Assisted Credit Assignment (NACA), this algorithm uses expectation signals based on both the input type 
and the output error to deliver defined levels of neuromodulator to selective synapses, and the local STDP form is modified in a non-linear
manner depending on the neuromodulator level, analogous to neuromodulator level-dependent synaptic modification in the brain3,4.
In shallow SNNs and ANNs, this NACA algorithm achieved high recognition accuracy with a substantial reduction of computational cost
in learning spatial and temporal classification tasks. 

Notably, for five different class-continuous learning (class-CL) tasks  with varying degrees of complexity, 
NACA markedly mitigated the catastrophic forgetting problem at low computational costs. 
Mapping synaptic weight changes in the hidden layer during class-CL tasks showed that NACA avoided excessive synapse potentiation
or depression, and preserved a substantial number of synapses with minimal modification. 
Thus, selective channeling of expectation signals into synapse subpopulations for neuromodulator level-dependent modulation of STDP
allows NACA to achieve efficient neural network learning with reduced catastrophic forgetting.
