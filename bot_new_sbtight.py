"""AlgoSoc pokerbot: equity-vs-range engine with a live opponent model.

Layout
  PARAMS / DEFAULT_PRIOR   generated config: the analyser and tuner rewrite these numbers
  tables                   precomputed preflop strength and all-in equity (see precompute.py)
  evaluator, Opp, Agent    fixed code
"""
import gc
import random
import time

_pc = time.perf_counter

#@CONFIG_START@
PARAMS = {"open": [0.0, 0.4, 0.45, 0.3, 0.21, 0.15, 0.1, 0.08], "bb_def": 0.0, "open_bb": 2.5, "tb_frac": 0.22, "call_frac": 0.75, "allin_margin": 0.03, "value": 0.6, "bet_edge": 0.015, "light3": 0.68, "war_eq": 0.56, "raise_min": 0.7, "raise_edge": 0.1, "shove_ev": 0.05, "raise": 0.78, "call_margin": 0.04, "early_margin": 0.03, "bet_med": 0.62, "bet_big": 0.85, "cbet_size": 0.45, "cbet_freq": 0.75, "bluff_edge": 0.03, "mc_ms": 1.0, "tb_eq": 0.6, "oop_fold": [0.72, 0.72, 0.72, 0.72], "oop_learn": 0, "oop_med_pot": 400, "commit_spr": 0.85, "commit_mult": 1.0, "f3_raise": 0.62, "f3_call": 0.08}
DEFAULT_PRIOR = {"vpip": 0.239, "pfr": 0.16, "tb": 0.08, "shove": 0.01, "af": 0.39, "ftb": 0.493, "cbig": 0.2, "fr": 0.782, "f3": 0.604}
FOLD_PRIOR = [[0.397, 0.548, 0.675, 0.795], [0.231, 0.401, 0.503, 0.616]]
BLUFF_PRIOR = [0.253, 0.215, 0.095]
#@CONFIG_END@

BUCKETS = [0.02, 0.04, 0.07, 0.11, 0.16, 0.23, 0.32, 0.45, 0.65, 1.0]
PCT = [0.6056, 0.9864, 0.9502, 0.9321, 0.9683, 0.9955, 0.9774, 0.9412, 0.914, 0.8597, 0.7783, 0.6968, 0.4676, 0.6878, 0.5226, 0.8959, 0.8507, 0.8688, 0.8778, 0.9593, 0.9231, 0.8869, 0.8145, 0.733, 0.6456, 0.4193, 0.6546, 0.5807, 0.3582, 0.7692, 0.7964, 0.8235, 0.8416, 0.905, 0.8326, 0.7873, 0.7149, 0.5867, 0.365, 0.6214, 0.5505, 0.4736, 0.2722, 0.6365, 0.7059, 0.7421, 0.7602, 0.8054, 0.7511, 0.6787, 0.5566, 0.3303, 0.6848, 0.5777, 0.4827, 0.371, 0.1772, 0.5686, 0.5958, 0.6606, 0.6697, 0.724, 0.6275, 0.5128, 0.3514, 0.6908, 0.6184, 0.4977, 0.4012, 0.3002, 0.1244, 0.4917, 0.5445, 0.5354, 0.5038, 0.6124, 0.4434, 0.3092, 0.6516, 0.6018, 0.5264, 0.4585, 0.3152, 0.2443, 0.0716, 0.4103, 0.3952, 0.4525, 0.3861, 0.4284, 0.2655, 0.5626, 0.5747, 0.5294, 0.4615, 0.3741, 0.2534, 0.187, 0.037, 0.279, 0.2911, 0.3213, 0.2353, 0.2262, 0.5189, 0.4857, 0.4766, 0.4374, 0.3424, 0.2504, 0.19, 0.1207, 0.0204, 0.2051, 0.1961, 0.1704, 0.1146, 0.4796, 0.4042, 0.4344, 0.3801, 0.3394, 0.2564, 0.2172, 0.1523, 0.0784, 0.0158, 0.1463, 0.1373, 0.0965, 0.3771, 0.3454, 0.3363, 0.3032, 0.2594, 0.2474, 0.184, 0.1282, 0.0754, 0.0528, 0.0113, 0.0875, 0.0618, 0.2971, 0.2851, 0.2413, 0.2202, 0.2112, 0.181, 0.1614, 0.1056, 0.0679, 0.0407, 0.0271, 0.0068, 0.0468, 0.2142, 0.1644, 0.1584, 0.1312, 0.1554, 0.1086, 0.1026, 0.0814, 0.0558, 0.0332, 0.0302, 0.0241, 0.0023]
EQR = [[0.181, 0.284, 0.37, 0.402, 0.426, 0.452, 0.453, 0.466, 0.489, 0.504], [0.142, 0.197, 0.259, 0.274, 0.28, 0.298, 0.3, 0.307, 0.319, 0.324], [0.148, 0.203, 0.258, 0.282, 0.29, 0.31, 0.305, 0.309, 0.32, 0.331], [0.142, 0.209, 0.263, 0.272, 0.287, 0.298, 0.31, 0.31, 0.335, 0.332], [0.136, 0.192, 0.242, 0.268, 0.283, 0.285, 0.297, 0.31, 0.323, 0.346], [0.118, 0.178, 0.239, 0.257, 0.28, 0.268, 0.282, 0.295, 0.304, 0.343], [0.123, 0.184, 0.242, 0.257, 0.289, 0.284, 0.288, 0.304, 0.32, 0.369], [0.113, 0.184, 0.246, 0.264, 0.274, 0.277, 0.292, 0.308, 0.341, 0.397], [0.119, 0.194, 0.237, 0.26, 0.273, 0.28, 0.302, 0.32, 0.367, 0.415], [0.127, 0.199, 0.247, 0.263, 0.279, 0.298, 0.32, 0.352, 0.39, 0.452], [0.162, 0.228, 0.259, 0.28, 0.293, 0.326, 0.353, 0.376, 0.406, 0.467], [0.207, 0.24, 0.271, 0.305, 0.326, 0.354, 0.389, 0.4, 0.448, 0.518], [0.261, 0.291, 0.32, 0.369, 0.395, 0.427, 0.463, 0.488, 0.512, 0.555], [0.183, 0.239, 0.282, 0.319, 0.32, 0.326, 0.333, 0.34, 0.347, 0.361], [0.188, 0.289, 0.377, 0.404, 0.436, 0.447, 0.47, 0.477, 0.515, 0.535], [0.161, 0.216, 0.268, 0.297, 0.295, 0.316, 0.313, 0.326, 0.335, 0.355], [0.165, 0.222, 0.279, 0.289, 0.315, 0.304, 0.325, 0.332, 0.339, 0.371], [0.149, 0.207, 0.26, 0.277, 0.294, 0.3, 0.307, 0.324, 0.328, 0.362], [0.13, 0.185, 0.253, 0.259, 0.281, 0.297, 0.3, 0.306, 0.334, 0.379], [0.122, 0.173, 0.236, 0.256, 0.283, 0.283, 0.291, 0.314, 0.327, 0.378], [0.123, 0.184, 0.241, 0.266, 0.275, 0.28, 0.297, 0.316, 0.344, 0.4], [0.118, 0.197, 0.247, 0.266, 0.275, 0.288, 0.311, 0.328, 0.371, 0.427], [0.127, 0.212, 0.249, 0.277, 0.278, 0.309, 0.33, 0.358, 0.394, 0.461], [0.158, 0.218, 0.251, 0.276, 0.303, 0.317, 0.35, 0.362, 0.415, 0.477], [0.205, 0.247, 0.281, 0.304, 0.333, 0.367, 0.396, 0.417, 0.452, 0.516], [0.264, 0.305, 0.323, 0.367, 0.393, 0.433, 0.466, 0.477, 0.512, 0.549], [0.187, 0.241, 0.287, 0.317, 0.323, 0.333, 0.35, 0.35, 0.352, 0.367], [0.199, 0.261, 0.309, 0.328, 0.341, 0.353, 0.349, 0.351, 0.357, 0.39], [0.188, 0.291, 0.386, 0.411, 0.445, 0.453, 0.476, 0.493, 0.524, 0.576], [0.179, 0.241, 0.289, 0.298, 0.32, 0.324, 0.331, 0.349, 0.352, 0.383], [0.163, 0.225, 0.281, 0.306, 0.314, 0.319, 0.315, 0.328, 0.341, 0.381], [0.154, 0.209, 0.258, 0.288, 0.298, 0.306, 0.306, 0.321, 0.342, 0.384], [0.135, 0.205, 0.258, 0.268, 0.279, 0.299, 0.31, 0.318, 0.356, 0.389], [0.122, 0.187, 0.236, 0.271, 0.277, 0.287, 0.308, 0.31, 0.352, 0.403], [0.125, 0.206, 0.241, 0.269, 0.282, 0.284, 0.326, 0.334, 0.38, 0.446], [0.135, 0.214, 0.255, 0.278, 0.285, 0.305, 0.342, 0.348, 0.398, 0.456], [0.176, 0.225, 0.259, 0.283, 0.31, 0.327, 0.364, 0.38, 0.422, 0.49], [0.21, 0.25, 0.282, 0.312, 0.334, 0.364, 0.391, 0.42, 0.462, 0.526], [0.268, 0.307, 0.329, 0.371, 0.403, 0.425, 0.459, 0.491, 0.52, 0.565], [0.19, 0.245, 0.294, 0.315, 0.325, 0.335, 0.336, 0.358, 0.361, 0.384], [0.202, 0.261, 0.305, 0.335, 0.335, 0.348, 0.354, 0.358, 0.372, 0.402], [0.216, 0.273, 0.323, 0.343, 0.35, 0.352, 0.384, 0.376, 0.394, 0.414], [0.201, 0.298, 0.392, 0.425, 0.439, 0.456, 0.496, 0.519, 0.55, 0.61], [0.191, 0.242, 0.292, 0.31, 0.335, 0.324, 0.345, 0.351, 0.36, 0.394], [0.172, 0.232, 0.276, 0.302, 0.313, 0.327, 0.331, 0.346, 0.366, 0.401], [0.153, 0.207, 0.268, 0.284, 0.296, 0.312, 0.32, 0.331, 0.372, 0.405], [0.145, 0.195, 0.256, 0.276, 0.289, 0.292, 0.314, 0.333, 0.375, 0.424], [0.122, 0.194, 0.246, 0.265, 0.269, 0.302, 0.307, 0.337, 0.384, 0.441], [0.142, 0.228, 0.25, 0.27, 0.289, 0.307, 0.333, 0.362, 0.405, 0.474], [0.169, 0.23, 0.267, 0.288, 0.301, 0.328, 0.37, 0.396, 0.423, 0.501], [0.221, 0.25, 0.277, 0.311, 0.342, 0.37, 0.406, 0.43, 0.467, 0.525], [0.278, 0.303, 0.335, 0.368, 0.401, 0.448, 0.477, 0.491, 0.528, 0.576], [0.171, 0.233, 0.289, 0.309, 0.322, 0.312, 0.329, 0.351, 0.341, 0.388], [0.183, 0.242, 0.308, 0.319, 0.328, 0.346, 0.348, 0.356, 0.366, 0.397], [0.204, 0.266, 0.302, 0.336, 0.335, 0.352, 0.351, 0.361, 0.385, 0.417], [0.225, 0.279, 0.32, 0.347, 0.366, 0.369, 0.365, 0.387, 0.398, 0.43], [0.192, 0.297, 0.404, 0.424, 0.457, 0.481, 0.497, 0.537, 0.577, 0.634], [0.176, 0.224, 0.294, 0.299, 0.328, 0.337, 0.328, 0.361, 0.38, 0.415], [0.164, 0.215, 0.279, 0.298, 0.313, 0.316, 0.34, 0.352, 0.383, 0.432], [0.156, 0.207, 0.265, 0.286, 0.294, 0.311, 0.332, 0.348, 0.385, 0.443], [0.139, 0.211, 0.265, 0.286, 0.302, 0.3, 0.325, 0.358, 0.396, 0.467], [0.135, 0.211, 0.261, 0.277, 0.295, 0.311, 0.339, 0.368, 0.402, 0.478], [0.178, 0.243, 0.26, 0.283, 0.31, 0.342, 0.37, 0.393, 0.436, 0.507], [0.216, 0.25, 0.293, 0.313, 0.334, 0.374, 0.415, 0.44, 0.472, 0.548], [0.262, 0.287, 0.314, 0.361, 0.401, 0.436, 0.468, 0.491, 0.538, 0.579], [0.163, 0.216, 0.277, 0.292, 0.299, 0.315, 0.322, 0.337, 0.348, 0.372], [0.169, 0.232, 0.292, 0.305, 0.324, 0.328, 0.336, 0.354, 0.369, 0.402], [0.185, 0.243, 0.301, 0.315, 0.322, 0.343, 0.356, 0.37, 0.388, 0.418], [0.212, 0.261, 0.307, 0.322, 0.351, 0.361, 0.363, 0.376, 0.398, 0.443], [0.22, 0.268, 0.322, 0.341, 0.353, 0.369, 0.38, 0.403, 0.41, 0.449], [0.197, 0.31, 0.397, 0.426, 0.475, 0.508, 0.536, 0.556, 0.606, 0.659], [0.178, 0.231, 0.288, 0.296, 0.325, 0.335, 0.337, 0.363, 0.4, 0.458], [0.167, 0.216, 0.272, 0.289, 0.306, 0.331, 0.338, 0.356, 0.411, 0.46], [0.148, 0.223, 0.261, 0.296, 0.296, 0.311, 0.343, 0.376, 0.42, 0.487], [0.149, 0.225, 0.262, 0.285, 0.299, 0.317, 0.347, 0.381, 0.435, 0.501], [0.171, 0.224, 0.264, 0.278, 0.316, 0.342, 0.374, 0.393, 0.447, 0.524], [0.216, 0.257, 0.287, 0.306, 0.348, 0.37, 0.413, 0.446, 0.496, 0.553], [0.265, 0.293, 0.322, 0.357, 0.411, 0.454, 0.481, 0.507, 0.554, 0.595], [0.165, 0.223, 0.277, 0.294, 0.307, 0.325, 0.336, 0.342, 0.36, 0.406], [0.163, 0.22, 0.269, 0.291, 0.317, 0.327, 0.33, 0.328, 0.366, 0.414], [0.178, 0.236, 0.29, 0.313, 0.324, 0.331, 0.35, 0.353, 0.378, 0.428], [0.189, 0.237, 0.301, 0.331, 0.338, 0.354, 0.358, 0.366, 0.396, 0.442], [0.209, 0.251, 0.315, 0.333, 0.359, 0.353, 0.369, 0.388, 0.409, 0.47], [0.21, 0.266, 0.315, 0.345, 0.356, 0.374, 0.375, 0.395, 0.444, 0.49], [0.188, 0.293, 0.401, 0.456, 0.49, 0.528, 0.558, 0.592, 0.639, 0.703], [0.173, 0.22, 0.282, 0.312, 0.322, 0.341, 0.35, 0.375, 0.417, 0.478], [0.167, 0.237, 0.277, 0.298, 0.326, 0.333, 0.353, 0.383, 0.433, 0.497], [0.155, 0.229, 0.272, 0.288, 0.303, 0.339, 0.372, 0.398, 0.45, 0.527], [0.186, 0.242, 0.268, 0.291, 0.327, 0.354, 0.381, 0.419, 0.475, 0.541], [0.215, 0.249, 0.286, 0.305, 0.343, 0.384, 0.422, 0.453, 0.52, 0.56], [0.252, 0.291, 0.318, 0.368, 0.412, 0.47, 0.5, 0.536, 0.557, 0.6], [0.163, 0.208, 0.279, 0.297, 0.314, 0.303, 0.338, 0.339, 0.386, 0.421], [0.164, 0.216, 0.279, 0.3, 0.323, 0.33, 0.331, 0.35, 0.382, 0.419], [0.167, 0.222, 0.281, 0.304, 0.317, 0.323, 0.334, 0.347, 0.388, 0.429], [0.178, 0.235, 0.295, 0.311, 0.335, 0.339, 0.349, 0.369, 0.402, 0.459], [0.2, 0.253, 0.311, 0.32, 0.339, 0.352, 0.363, 0.388, 0.418, 0.474], [0.199, 0.255, 0.314, 0.33, 0.353, 0.356, 0.372, 0.391, 0.438, 0.5], [0.215, 0.261, 0.32, 0.338, 0.356, 0.368, 0.396, 0.41, 0.448, 0.499], [0.183, 0.311, 0.423, 0.487, 0.523, 0.551, 0.598, 0.634, 0.663, 0.716], [0.157, 0.243, 0.29, 0.319, 0.326, 0.342, 0.368, 0.403, 0.456, 0.518], [0.17, 0.24, 0.286, 0.307, 0.329, 0.352, 0.38, 0.418, 0.474, 0.543], [0.187, 0.244, 0.276, 0.309, 0.34, 0.373, 0.405, 0.445, 0.492, 0.563], [0.215, 0.251, 0.298, 0.317, 0.367, 0.405, 0.453, 0.486, 0.536, 0.59], [0.252, 0.283, 0.327, 0.391, 0.44, 0.473, 0.518, 0.552, 0.584, 0.619], [0.168, 0.235, 0.279, 0.304, 0.313, 0.334, 0.346, 0.376, 0.4, 0.458], [0.169, 0.237, 0.277, 0.311, 0.313, 0.321, 0.345, 0.362, 0.405, 0.464], [0.17, 0.24, 0.282, 0.317, 0.314, 0.33, 0.349, 0.38, 0.406, 0.465], [0.175, 0.237, 0.289, 0.31, 0.309, 0.33, 0.349, 0.375, 0.417, 0.471], [0.186, 0.244, 0.304, 0.313, 0.337, 0.341, 0.363, 0.383, 0.43, 0.488], [0.19, 0.261, 0.316, 0.328, 0.341, 0.356, 0.37, 0.393, 0.455, 0.511], [0.201, 0.267, 0.306, 0.336, 0.355, 0.365, 0.398, 0.412, 0.47, 0.531], [0.199, 0.279, 0.325, 0.34, 0.363, 0.387, 0.4, 0.451, 0.486, 0.542], [0.184, 0.403, 0.467, 0.537, 0.57, 0.604, 0.641, 0.67, 0.717, 0.744], [0.165, 0.267, 0.291, 0.327, 0.357, 0.375, 0.42, 0.456, 0.495, 0.551], [0.199, 0.274, 0.285, 0.33, 0.359, 0.4, 0.457, 0.472, 0.522, 0.567], [0.231, 0.283, 0.313, 0.363, 0.397, 0.442, 0.494, 0.52, 0.558, 0.595], [0.272, 0.325, 0.35, 0.431, 0.468, 0.53, 0.564, 0.593, 0.599, 0.631], [0.161, 0.249, 0.29, 0.304, 0.31, 0.325, 0.362, 0.379, 0.43, 0.474], [0.169, 0.239, 0.275, 0.303, 0.321, 0.336, 0.37, 0.38, 0.418, 0.485], [0.183, 0.256, 0.29, 0.313, 0.318, 0.349, 0.372, 0.386, 0.425, 0.488], [0.183, 0.256, 0.297, 0.312, 0.326, 0.337, 0.362, 0.397, 0.448, 0.502], [0.184, 0.247, 0.293, 0.311, 0.32, 0.35, 0.375, 0.403, 0.428, 0.506], [0.192, 0.252, 0.297, 0.313, 0.34, 0.354, 0.385, 0.41, 0.47, 0.53], [0.201, 0.271, 0.321, 0.326, 0.352, 0.371, 0.401, 0.437, 0.476, 0.537], [0.202, 0.27, 0.323, 0.337, 0.355, 0.386, 0.422, 0.453, 0.502, 0.558], [0.19, 0.287, 0.321, 0.35, 0.375, 0.399, 0.452, 0.479, 0.526, 0.575], [0.289, 0.481, 0.532, 0.584, 0.625, 0.653, 0.685, 0.719, 0.742, 0.77], [0.204, 0.278, 0.321, 0.345, 0.378, 0.42, 0.456, 0.489, 0.531, 0.58], [0.245, 0.287, 0.351, 0.369, 0.406, 0.471, 0.508, 0.532, 0.567, 0.606], [0.285, 0.356, 0.378, 0.451, 0.527, 0.557, 0.58, 0.608, 0.614, 0.634], [0.21, 0.255, 0.285, 0.31, 0.339, 0.35, 0.378, 0.405, 0.443, 0.506], [0.203, 0.265, 0.286, 0.314, 0.333, 0.364, 0.389, 0.405, 0.458, 0.512], [0.21, 0.261, 0.296, 0.319, 0.344, 0.359, 0.397, 0.417, 0.449, 0.518], [0.221, 0.273, 0.296, 0.315, 0.348, 0.368, 0.408, 0.418, 0.472, 0.531], [0.208, 0.26, 0.305, 0.321, 0.347, 0.363, 0.404, 0.427, 0.468, 0.54], [0.211, 0.254, 0.301, 0.318, 0.332, 0.372, 0.395, 0.426, 0.481, 0.545], [0.227, 0.271, 0.309, 0.333, 0.351, 0.389, 0.425, 0.445, 0.496, 0.557], [0.23, 0.287, 0.316, 0.339, 0.364, 0.393, 0.439, 0.469, 0.515, 0.582], [0.23, 0.306, 0.323, 0.376, 0.391, 0.429, 0.475, 0.512, 0.536, 0.594], [0.246, 0.318, 0.341, 0.379, 0.404, 0.454, 0.476, 0.515, 0.552, 0.617], [0.466, 0.581, 0.61, 0.664, 0.686, 0.714, 0.726, 0.742, 0.758, 0.802], [0.28, 0.327, 0.357, 0.407, 0.45, 0.498, 0.536, 0.547, 0.585, 0.621], [0.312, 0.397, 0.443, 0.533, 0.576, 0.589, 0.599, 0.625, 0.631, 0.649], [0.245, 0.28, 0.317, 0.339, 0.376, 0.393, 0.417, 0.441, 0.472, 0.542], [0.249, 0.284, 0.321, 0.334, 0.365, 0.391, 0.43, 0.456, 0.475, 0.543], [0.257, 0.281, 0.323, 0.343, 0.376, 0.402, 0.433, 0.451, 0.485, 0.55], [0.255, 0.282, 0.328, 0.344, 0.372, 0.395, 0.436, 0.464, 0.499, 0.566], [0.259, 0.285, 0.329, 0.348, 0.371, 0.406, 0.441, 0.468, 0.512, 0.56], [0.248, 0.291, 0.322, 0.346, 0.371, 0.416, 0.45, 0.471, 0.528, 0.566], [0.253, 0.283, 0.315, 0.345, 0.386, 0.43, 0.457, 0.492, 0.54, 0.579], [0.251, 0.289, 0.319, 0.372, 0.403, 0.432, 0.479, 0.508, 0.551, 0.601], [0.263, 0.333, 0.344, 0.378, 0.419, 0.47, 0.512, 0.543, 0.579, 0.618], [0.279, 0.339, 0.379, 0.403, 0.447, 0.496, 0.54, 0.544, 0.583, 0.621], [0.314, 0.367, 0.391, 0.451, 0.482, 0.516, 0.561, 0.573, 0.602, 0.633], [0.63, 0.687, 0.716, 0.737, 0.748, 0.769, 0.775, 0.784, 0.8, 0.817], [0.367, 0.467, 0.532, 0.59, 0.605, 0.625, 0.64, 0.649, 0.648, 0.653], [0.298, 0.339, 0.361, 0.396, 0.43, 0.459, 0.474, 0.512, 0.537, 0.569], [0.292, 0.329, 0.353, 0.394, 0.435, 0.473, 0.495, 0.507, 0.547, 0.576], [0.305, 0.343, 0.369, 0.4, 0.442, 0.472, 0.501, 0.512, 0.544, 0.58], [0.307, 0.34, 0.367, 0.404, 0.437, 0.47, 0.5, 0.518, 0.562, 0.609], [0.292, 0.334, 0.356, 0.399, 0.431, 0.475, 0.503, 0.536, 0.562, 0.61], [0.296, 0.325, 0.354, 0.393, 0.447, 0.477, 0.507, 0.543, 0.573, 0.612], [0.285, 0.333, 0.362, 0.403, 0.446, 0.487, 0.526, 0.565, 0.58, 0.608], [0.291, 0.333, 0.358, 0.422, 0.469, 0.5, 0.551, 0.574, 0.602, 0.633], [0.29, 0.358, 0.384, 0.453, 0.488, 0.557, 0.585, 0.61, 0.623, 0.642], [0.308, 0.383, 0.411, 0.487, 0.543, 0.587, 0.618, 0.631, 0.628, 0.648], [0.359, 0.432, 0.478, 0.551, 0.584, 0.614, 0.63, 0.66, 0.646, 0.662], [0.398, 0.487, 0.555, 0.607, 0.628, 0.651, 0.657, 0.663, 0.66, 0.671], [0.798, 0.814, 0.836, 0.845, 0.841, 0.835, 0.842, 0.84, 0.838, 0.851]]
EQ3 = [0.221, 0.138, 0.146, 0.153, 0.142, 0.142, 0.154, 0.162, 0.171, 0.184, 0.201, 0.22, 0.254, 0.185, 0.235, 0.162, 0.172, 0.166, 0.164, 0.158, 0.168, 0.178, 0.192, 0.208, 0.23, 0.263, 0.191, 0.204, 0.266, 0.189, 0.182, 0.175, 0.172, 0.173, 0.189, 0.198, 0.214, 0.238, 0.272, 0.196, 0.211, 0.227, 0.289, 0.203, 0.198, 0.193, 0.19, 0.194, 0.206, 0.223, 0.246, 0.281, 0.188, 0.204, 0.224, 0.234, 0.321, 0.215, 0.217, 0.211, 0.21, 0.211, 0.231, 0.252, 0.273, 0.185, 0.198, 0.219, 0.235, 0.249, 0.342, 0.229, 0.227, 0.233, 0.238, 0.234, 0.268, 0.286, 0.193, 0.202, 0.214, 0.231, 0.25, 0.263, 0.377, 0.246, 0.256, 0.252, 0.262, 0.272, 0.295, 0.207, 0.206, 0.213, 0.23, 0.246, 0.268, 0.287, 0.404, 0.277, 0.276, 0.276, 0.298, 0.307, 0.215, 0.221, 0.227, 0.234, 0.25, 0.274, 0.29, 0.31, 0.455, 0.302, 0.31, 0.321, 0.343, 0.225, 0.239, 0.237, 0.244, 0.251, 0.273, 0.287, 0.306, 0.339, 0.495, 0.323, 0.33, 0.357, 0.245, 0.25, 0.254, 0.261, 0.271, 0.275, 0.3, 0.321, 0.346, 0.36, 0.535, 0.347, 0.373, 0.262, 0.267, 0.276, 0.283, 0.292, 0.3, 0.304, 0.327, 0.358, 0.367, 0.383, 0.578, 0.381, 0.292, 0.301, 0.309, 0.32, 0.31, 0.326, 0.336, 0.34, 0.369, 0.385, 0.389, 0.414, 0.636]
EQ6 = [0.144, 0.078, 0.085, 0.091, 0.077, 0.072, 0.077, 0.08, 0.088, 0.095, 0.104, 0.123, 0.139, 0.116, 0.149, 0.099, 0.101, 0.092, 0.084, 0.078, 0.081, 0.089, 0.1, 0.106, 0.118, 0.141, 0.119, 0.13, 0.154, 0.108, 0.102, 0.094, 0.091, 0.083, 0.097, 0.102, 0.111, 0.122, 0.148, 0.127, 0.14, 0.149, 0.157, 0.118, 0.11, 0.102, 0.103, 0.094, 0.107, 0.114, 0.132, 0.152, 0.116, 0.132, 0.144, 0.153, 0.172, 0.121, 0.116, 0.11, 0.112, 0.11, 0.12, 0.134, 0.147, 0.115, 0.128, 0.135, 0.145, 0.158, 0.185, 0.132, 0.131, 0.127, 0.125, 0.124, 0.14, 0.159, 0.12, 0.12, 0.13, 0.145, 0.153, 0.17, 0.205, 0.137, 0.139, 0.142, 0.142, 0.146, 0.164, 0.121, 0.124, 0.129, 0.14, 0.155, 0.166, 0.178, 0.223, 0.162, 0.16, 0.164, 0.166, 0.171, 0.135, 0.134, 0.135, 0.139, 0.147, 0.166, 0.179, 0.199, 0.251, 0.189, 0.189, 0.191, 0.195, 0.137, 0.139, 0.145, 0.15, 0.149, 0.167, 0.178, 0.197, 0.218, 0.288, 0.199, 0.203, 0.207, 0.145, 0.149, 0.152, 0.157, 0.161, 0.166, 0.184, 0.197, 0.225, 0.236, 0.332, 0.219, 0.221, 0.157, 0.159, 0.166, 0.176, 0.173, 0.183, 0.186, 0.202, 0.224, 0.239, 0.254, 0.378, 0.244, 0.179, 0.183, 0.194, 0.194, 0.186, 0.196, 0.201, 0.213, 0.233, 0.25, 0.26, 0.274, 0.432]

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: RANKS.index(r) * 4 + SUITS.index(s) for r in RANKS for s in SUITS}

POP = [bin(i).count("1") for i in range(8192)]
STRAIGHT = [0] * 8192
for _m in range(8192):
    _best = 0
    for _hi in range(12, 3, -1):
        _w = 0x1F << (_hi - 4)
        if _m & _w == _w:
            _best = _hi
            break
    if not _best and (_m & 0x100F) == 0x100F:
        _best = 3
    STRAIGHT[_m] = _best


def _top(m, n):
    out = 0
    for _ in range(n):
        if not m:
            break
        b = 1 << (m.bit_length() - 1)
        out |= b
        m ^= b
    return out


TOP5 = [_top(m, 5) for m in range(8192)]
TOP3 = [_top(m, 3) for m in range(8192)]
TOP2 = [_top(m, 2) for m in range(8192)]


def ev(cards):
    m1 = m2 = m3 = m4 = 0
    s0 = s1 = s2 = s3 = 0
    for c in cards:
        b = 1 << (c >> 2)
        s = c & 3
        if s == 0:
            s0 |= b
        elif s == 1:
            s1 |= b
        elif s == 2:
            s2 |= b
        else:
            s3 |= b
        m4 |= m3 & b
        m3 |= m2 & b
        m2 |= m1 & b
        m1 |= b
    for sm in (s0, s1, s2, s3):
        if POP[sm] >= 5:
            st = STRAIGHT[sm]
            if st:
                return (8 << 26) | st
            return (5 << 26) | TOP5[sm]
    if m4:
        q = m4.bit_length() - 1
        return (7 << 26) | (q << 4) | ((m1 ^ (1 << q)).bit_length() - 1)
    t = 0
    if m3:
        t = m3.bit_length() - 1
        r = m2 ^ (1 << t)
        if r:
            return (6 << 26) | (t << 4) | (r.bit_length() - 1)
    st = STRAIGHT[m1]
    if st:
        return (4 << 26) | st
    if m3:
        return (3 << 26) | (t << 13) | TOP2[m1 ^ (1 << t)]
    if m2:
        p = m2.bit_length() - 1
        r = m2 ^ (1 << p)
        if r:
            p2 = r.bit_length() - 1
            return (2 << 26) | (p << 8) | (p2 << 4) | ((m1 ^ (1 << p) ^ (1 << p2)).bit_length() - 1)
        return (1 << 26) | (p << 13) | TOP3[m1 ^ (1 << p)]
    return TOP5[m1]


RB = [1 << (c >> 2) for c in range(52)]


def prep(cards):
    """Evaluator state for up to five cards, ready to be completed by two more with ev2.

    (rank masks by multiplicity 1..4, the suit that can still make a flush or -1, that suit's rank mask)"""
    m1 = m2 = m3 = m4 = 0
    s = [0, 0, 0, 0]
    for c in cards:
        b = RB[c]
        s[c & 3] |= b
        m4 |= m3 & b
        m3 |= m2 & b
        m2 |= m1 & b
        m1 |= b
    for i in range(4):
        if POP[s[i]] >= 3:
            return (m1, m2, m3, m4, i, s[i])
    return (m1, m2, m3, m4, -1, 0)


def ev2(pre, c1, c2):
    """ev(cards + [c1, c2]) where pre = prep(cards). Same values as ev."""
    m1, m2, m3, m4, fs, fm = pre
    b = RB[c1]
    m4 |= m3 & b
    m3 |= m2 & b
    m2 |= m1 & b
    m1 |= b
    b2 = RB[c2]
    m4 |= m3 & b2
    m3 |= m2 & b2
    m2 |= m1 & b2
    m1 |= b2
    if fs >= 0:
        if (c1 & 3) == fs:
            fm |= b
        if (c2 & 3) == fs:
            fm |= b2
        if POP[fm] >= 5:
            st = STRAIGHT[fm]
            if st:
                return (8 << 26) | st
            return (5 << 26) | TOP5[fm]
    if m4:
        q = m4.bit_length() - 1
        return (7 << 26) | (q << 4) | ((m1 ^ (1 << q)).bit_length() - 1)
    t = 0
    if m3:
        t = m3.bit_length() - 1
        r = m2 ^ (1 << t)
        if r:
            return (6 << 26) | (t << 4) | (r.bit_length() - 1)
    st = STRAIGHT[m1]
    if st:
        return (4 << 26) | st
    if m3:
        return (3 << 26) | (t << 13) | TOP2[m1 ^ (1 << t)]
    if m2:
        p = m2.bit_length() - 1
        r = m2 ^ (1 << p)
        if r:
            p2 = r.bit_length() - 1
            return (2 << 26) | (p << 8) | (p2 << 4) | ((m1 ^ (1 << p) ^ (1 << p2)).bit_length() - 1)
        return (1 << 26) | (p << 13) | TOP3[m1 ^ (1 << p)]
    return TOP5[m1]


def cls(c1, c2):
    r1 = c1 >> 2
    r2 = c2 >> 2
    if r1 == r2:
        return r1 * 14
    if r1 < r2:
        r1, r2 = r2, r1
    if (c1 & 3) == (c2 & 3):
        return r1 * 13 + r2
    return r2 * 13 + r1


COMBOS = sorted(((a, b) for a in range(52) for b in range(a + 1, 52)), key=lambda x: PCT[cls(x[0], x[1])])
NCOMB = len(COMBOS)


def eqr(c, t):
    """All-in equity of hand class c against one opponent holding the top t of hands."""
    row = EQR[c]
    if t <= BUCKETS[0]:
        return row[0]
    for i in range(1, len(BUCKETS)):
        if t <= BUCKETS[i]:
            f = (t - BUCKETS[i - 1]) / (BUCKETS[i] - BUCKETS[i - 1])
            return row[i - 1] + f * (row[i] - row[i - 1])
    return row[-1]


class Opp:
    """Running stats for one seat. Every estimate is the observed count blended with a prior."""

    __slots__ = ("n", "vpip", "pfr", "tbo", "tb", "shv", "ag", "pa", "fb", "fd", "bigf", "bigc",
                 "sr_n", "sr_s", "sc_n", "sc_s", "an", "aw", "pr",
                 "fbk", "fdk", "ank", "awk", "f3o", "f3f", "fro", "frf", "r4o", "r4", "pjo", "pjc", "pbo", "pbc", "sdn", "sds",
                 "tbc", "tbco", "r4c", "r4co", "sd1n", "sd1s", "sd4n", "sd4s", "bbo", "bbf", "ipp", "ipd")

    def __init__(self, pr):
        self.n = self.vpip = self.pfr = self.tbo = self.tb = self.shv = 0
        self.ag = self.pa = self.fb = self.fd = self.bigf = self.bigc = 0
        self.sr_n = self.sc_n = self.an = self.aw = 0
        self.sr_s = self.sc_s = 0.0
        self.pr = pr
        # faced a bet postflop / folded to it. [stage][size]: stage 0 = first bet this seat faces in the hand,
        # stage 1 = it has already called or bet postflop. Sizes: small, medium, big, overbet.
        self.fbk = [[0, 0, 0, 0], [0, 0, 0, 0]]
        self.fdk = [[0, 0, 0, 0], [0, 0, 0, 0]]
        self.ank = [0, 0, 0]   # showdowns after betting small / medium / big
        self.awk = [0, 0, 0]   # ... holding nothing beyond the board
        self.f3o = self.f3f = self.fro = self.frf = self.r4o = self.r4 = self.pjo = self.pjc = self.pbo = self.pbc = 0
        # Shown hands by preflop line: 0 opened, 1 re-raised, 2 called a raise, 3 called a shove, 4 shoved.
        # sdn = count, sds = sum of strength percentiles (a range "top t" shows hands averaging t/2).
        self.sdn = [0, 0, 0, 0, 0]
        self.sds = [0.0, 0.0, 0.0, 0.0, 0.0]
        # Re-raising is tracked in two contexts, because everyone re-raises a maniac far wider than they
        # re-raise a normal player: index 0 = the raise they faced came from a normal range, 1 = from a wide one.
        self.tbc = [0, 0]     # re-raised an open
        self.tbco = [0, 0]    # ... chances to
        self.r4c = [0, 0]     # raised again over a re-raise
        self.r4co = [0, 0]    # ... chances to
        self.sd1n = [0, 0]    # shown hands after re-raising, by context
        self.sd1s = [0.0, 0.0]
        self.sd4n = [0, 0]    # shown hands after shoving, by context
        self.bbo = self.bbf = 0   # in the big blind facing one raise / folded it
        # Heads-up flop/turn bets faced while acting after the bettor: sum of fold_at predictions / real folds.
        self.ipp = 0.0
        self.ipd = 0
        self.sd4s = [0.0, 0.0]

    def vp(self):
        return (self.vpip + self.pr["vpip"] * 10) / (self.n + 10)

    def pf(self):
        return (self.pfr + self.pr["pfr"] * 10) / (self.n + 10)

    def t3(self):
        return (self.tb + self.pr["tb"] * 15) / (self.tbo + 15)

    def sh(self):
        return (self.shv + self.pr["shove"] * 15) / (self.n + 15)

    def af(self):
        return (self.ag + self.pr["af"] * 10) / (self.ag + self.pa + 10)

    def ftb(self):
        return (self.fd + self.pr["ftb"] * 8) / (self.fb + 8)

    def cbig(self):
        return (self.bigc + self.pr["cbig"] * 4) / (self.bigf + 4)

    def qj(self):
        """P(calls a preflop shove). Stays at a low default until this seat has shown it calls big bets."""
        if self.pjo >= 3:
            q = (self.pjc + 0.08) / (self.pjo + 2.0)
        elif self.pbo >= 5 and self.pbc >= 0.8 * self.pbo:
            q = 0.9 * self.pbc / self.pbo
        else:
            q = 0.04
        return 0.97 if q > 0.97 else q

    def t3c(self, ctx):
        """P(re-raise | facing an open) in the given context."""
        if ctx:
            return (self.tbc[1] + 0.12 * 8) / (self.tbco[1] + 8)
        return (self.tbc[0] + self.pr["tb"] * 15) / (self.tbco[0] + 15)

    def t4c(self, ctx):
        """P(raise again | facing a re-raise) in the given context."""
        if ctx:
            return (self.r4c[1] + 0.35 * 6) / (self.r4co[1] + 6)
        return (self.r4c[0] + 0.18 * 6) / (self.r4co[0] + 6)

    def wide(self, lvl):
        """Is this seat's raise at the given level a wide range?"""
        if lvl <= 1:
            return self.pf() >= 0.28
        return self.t3c(0) >= 0.2

    def t4(self):
        """P(raise again | facing a 3-bet or more)."""
        return (self.r4 + 0.03 * 10) / (self.r4o + 10)

    def fr(self):
        """P(fold | facing a single preflop raise)."""
        return (self.frf + self.pr.get("fr", 0.78) * 8) / (self.fro + 8)

    def bbfold(self):
        """P(fold | in the big blind facing a single raise). Field average here is about 0.60."""
        return (self.bbf + 0.60 * 6) / (self.bbo + 6)

    def f3(self):
        """P(fold | opened and got 3-bet)."""
        return (self.f3f + self.pr.get("f3", 0.5) * 4) / (self.f3o + 4)

    def fold_at(self, kb, stage, tfb, tfd):
        """P(fold | facing a postflop bet of size bucket kb at this stage of the hand).

        Shrunk toward the whole table's behaviour (tfb/tfd), since most opponents share the same habits
        and one seat alone rarely faces enough big bets in a round to measure."""
        fb = self.fbk[stage]
        fd = self.fdk[stage]
        tb = tfb[stage]
        td = tfd[stage]
        fp = FOLD_PRIOR[stage]
        trate = (td[0] + td[1] + td[2] + td[3] + fp[1] * 8.0) / (tb[0] + tb[1] + tb[2] + tb[3] + 8.0)
        base = (fd[0] + fd[1] + fd[2] + fd[3] + trate * 6.0) / (fb[0] + fb[1] + fb[2] + fb[3] + 6.0)
        tk = (td[kb] + fp[kb] * 6.0) / (tb[kb] + 6.0)
        prior = base + tk - trate
        f = (fd[kb] + prior * 5.0) / (fb[kb] + 5.0)
        return 0.0 if f < 0.0 else (0.95 if f > 0.95 else f)

    def hon(self, kb):
        """How much a bet of size bucket kb should tighten this seat's range (1.0 = typical)."""
        n = self.ank[kb]
        if n >= 4:
            br = self.awk[kb] / float(n)
        elif self.an >= 4:
            br = self.aw / float(self.an)
        else:
            br = BLUFF_PRIOR[kb]
        h = 1.5 - 2.5 * br
        return 0.25 if h < 0.25 else h


class Agent:
    def __init__(self, params=None):
        # params overrides entries of PARAMS (used by sim variants: 'bot.py:{"mc_ms": 2.0}').
        self.P = dict(PARAMS, **params) if params else PARAMS
        self.n = 8
        self.me = 0
        self.opp = [Opp(DEFAULT_PRIOR) for _ in range(8)]
        self.used = 0.0
        self.hand = -1
        self.cache = {}
        self.chk = set()
        self.tfb = [[0, 0, 0, 0], [0, 0, 0, 0]]
        self.tfd = [[0, 0, 0, 0], [0, 0, 0, 0]]
        self.tipp = 0.0       # whole table: as Opp.ipp / Opp.ipd
        self.tipd = 0
        self.errs = 0
        self.last_err = ""
        self.btn = 0
        self.sent = None      # (hand, index of this action among ours, action) of the last reply
        self.tmo = 0          # replies of ours the dealer replaced with check/fold (we were too slow)
        self.scale = 1.0      # thinking-time multiplier, halved on every detected timeout

    def on_table_start(self, info):
        try:
            self.me = info.get("seat", 0)
            self.n = info.get("num_players", 8)
            self.opp = [Opp(DEFAULT_PRIOR) for _ in range(self.n)]
        except Exception:
            pass

    # ------------------------------------------------------------------ entry points
    def act(self, state):
        t0 = _pc()
        out = None
        try:
            out = self._act(state, t0)
        except Exception as ex:
            out = None
            self.errs += 1
            self.last_err = repr(ex)
        if not out:
            try:
                out = {"action": "check" if "check" in state["legal_actions"] else "fold"}
            except Exception:
                out = {"action": "fold"}
        try:
            me = self.me
            k = 0
            for h in state["history"]:
                if h["seat"] == me and h["action"] != "small_blind" and h["action"] != "big_blind":
                    k += 1
            self.sent = (state["hand_number"], k, out["action"])
        except Exception:
            self.sent = None
        self.used += _pc() - t0
        return out

    def _check_sent(self, hand, history):
        """Did the dealer record what we last replied? If it recorded a fold/check instead, we timed out."""
        s = self.sent
        self.sent = None
        if not s or s[0] != hand:
            return
        me = self.me
        k = 0
        for h in history:
            if h["seat"] == me and h["action"] != "small_blind" and h["action"] != "big_blind":
                if k == s[1]:
                    got = h["action"]
                    if (got == "fold" and s[2] != "fold") or (got == "check" and s[2] == "raise"):
                        self.tmo += 1
                        self.scale *= 0.5
                    return
                k += 1

    def on_hand_end(self, summary):
        try:
            self._learn(summary)
            if summary.get("hand_number", 1) % 50 == 0:
                gc.collect()
        except Exception as ex:
            self.errs += 1
            self.last_err = repr(ex)

    # ------------------------------------------------------------------ learning
    def _learn(self, summary):
        self._check_sent(summary.get("hand_number"), summary["history"])
        n = self.n
        opp = self.opp
        bets = [0] * n
        pot = 0
        cur = 0
        street = "preflop"
        L = 0
        vp = set()
        pr = set()
        agg = set()
        jam = set()
        opener = -1
        opener_done = False
        szb = {}
        inpost = set()
        maxlvl = {}
        jamc = set()
        rctx = {}
        lr = -1
        bbs = -1
        nfold = 0
        first = -1
        for h in summary["history"]:
            s = h["seat"]
            a = h["action"]
            amt = h.get("amount") or 0
            if h["street"] != street:
                street = h["street"]
                bets = [0] * n
                cur = 0
                first = s     # postflop the seat out of position acts first
            if a == "small_blind" or a == "big_blind":
                bets[s] = amt
                pot += amt
                if amt > cur:
                    cur = amt
                if a == "big_blind":
                    bbs = s
                continue
            o = opp[s]
            tc = cur - bets[s]
            if street == "preflop":
                if L >= 1:
                    o.tbo += 1
                    if a == "raise":
                        o.tb += 1
                    ctx = 1 if (lr >= 0 and opp[lr].wide(L)) else 0
                    if L == 1:
                        o.tbco[ctx] += 1
                        if a == "raise":
                            o.tbc[ctx] += 1
                    else:
                        o.r4co[ctx] += 1
                        if a == "raise":
                            o.r4c[ctx] += 1
                    if a == "raise":
                        rctx[s] = ctx
                    if L >= 2:
                        o.r4o += 1
                        if a == "raise":
                            o.r4 += 1
                    if L == 1 and s != opener:
                        o.fro += 1
                        if a == "fold":
                            o.frf += 1
                        if s == bbs:
                            o.bbo += 1
                            if a == "fold":
                                o.bbf += 1
                    elif L == 2 and s == opener and not opener_done:
                        opener_done = True
                        o.f3o += 1
                        if a == "fold":
                            o.f3f += 1
                if tc >= 200:
                    o.bigf += 1
                    if a != "fold":
                        o.bigc += 1
                    if s not in pr:
                        # Cold decisions only: a seat that already raised this hand holds a premium and
                        # would make every opponent look like it calls shoves.
                        o.pbo += 1
                        if a != "fold":
                            o.pbc += 1
                        if tc >= 600:
                            o.pjo += 1
                            if a != "fold":
                                o.pjc += 1
                if a == "raise":
                    vp.add(s)
                    pr.add(s)
                    L += 1
                    maxlvl[s] = L
                    lr = s
                    if L == 1:
                        opener = s
                    if amt >= 800:
                        jam.add(s)
                elif a == "call":
                    vp.add(s)
                    if tc >= 600:
                        jamc.add(s)
            else:
                if tc > 0:
                    o.fb += 1
                    before = pot - tc
                    fr_ = tc / float(before) if before > 0 else 1.0
                    kb = 0 if fr_ < 0.5 else (1 if fr_ < 0.95 else (2 if fr_ < 1.6 else 3))
                    stg = 1 if s in inpost else 0
                    if s != first and s != self.me and street != "river" and n - nfold == 2 and bets[s] == 0:
                        # In position, heads-up, facing the first bet of the street: how often does this seat
                        # really fold compared with what fold_at says? (Read before this hand is counted.)
                        pv = o.fold_at(kb, stg, self.tfb, self.tfd)
                        o.ipp += pv
                        self.tipp += pv
                        if a == "fold":
                            o.ipd += 1
                            self.tipd += 1
                    o.fbk[stg][kb] += 1
                    if a == "fold":
                        o.fdk[stg][kb] += 1
                    if s != self.me:
                        self.tfb[stg][kb] += 1
                        if a == "fold":
                            self.tfd[stg][kb] += 1
                    if tc >= 0.8 * pot:
                        o.bigf += 1
                        if a != "fold":
                            o.bigc += 1
                if a == "raise":
                    o.ag += 1
                    agg.add(s)
                    base = pot + tc
                    fr_ = (amt - cur) / float(base) if base > 0 else 1.0
                    szb.setdefault(s, set()).add(0 if fr_ < 0.5 else (1 if fr_ < 0.95 else 2))
                elif a == "call" or a == "check":
                    o.pa += 1
                elif a == "fold" and tc > 0:
                    o.fd += 1
                if a == "raise" or a == "call":
                    inpost.add(s)
            if a == "raise":
                pot += amt - bets[s]
                bets[s] = amt
                cur = amt
            elif a == "call":
                pot += amt
                bets[s] += amt
            elif a == "fold":
                nfold += 1
        for s in range(n):
            o = opp[s]
            o.n += 1
            if s in vp:
                o.vpip += 1
            if s in pr:
                o.pfr += 1
            if s in jam:
                o.shv += 1
        shown = summary.get("shown") or {}
        if shown:
            board = [CARD[x] for x in summary.get("board", [])]
            bcat = (ev(board) >> 26) if len(board) == 5 else -1
            for k, cards in shown.items():
                s = int(k)
                if s == self.me or len(cards) != 2:
                    continue
                o = opp[s]
                c1 = CARD[cards[0]]
                c2 = CARD[cards[1]]
                p = PCT[cls(c1, c2)]
                if s in jam:
                    cat = 4
                elif s in pr:
                    cat = 1 if maxlvl.get(s, 1) >= 2 else 0
                elif s in jamc:
                    cat = 3
                elif s in vp:
                    cat = 2
                else:
                    cat = -1
                if cat >= 0:
                    o.sdn[cat] += 1
                    o.sds[cat] += p
                    cx = rctx.get(s, 0)
                    if cat == 1:
                        o.sd1n[cx] += 1
                        o.sd1s[cx] += p
                    elif cat == 4:
                        o.sd4n[cx] += 1
                        o.sd4s[cx] += p
                if s in agg and bcat >= 0:
                    weak = (ev(board + [c1, c2]) >> 26) <= bcat
                    o.an += 1
                    if weak:
                        o.aw += 1
                    for kb in szb.get(s, ()):
                        o.ank[kb] += 1
                        if weak:
                            o.awk[kb] += 1

    # ------------------------------------------------------------------ this hand so far
    def _scan(self, st):
        n = self.n
        bets = [0] * n
        pot = 0
        cur = 0
        street = "preflop"
        L = 0
        lastr = -1
        limp = 0
        callers = 0
        role = {}
        pts = [0.0] * n
        cp = [0.0] * n
        opp = self.opp
        self.chk = set()
        for h in st["history"]:
            s = h["seat"]
            a = h["action"]
            amt = h.get("amount") or 0
            if h["street"] != street:
                street = h["street"]
                bets = [0] * n
                cur = 0
                self.chk = set()
            if a == "small_blind" or a == "big_blind":
                bets[s] = amt
                pot += amt
                if amt > cur:
                    cur = amt
                continue
            tc = cur - bets[s]
            if a == "raise":
                if street == "preflop":
                    cx = 1 if (L >= 1 and lastr >= 0 and opp[lastr].wide(L)) else 0
                    L += 1
                    lastr = s
                    callers = 0
                    role[s] = ("r", L, amt >= 800, cx)
                else:
                    base = pot + tc
                    frac = (amt - cur) / base if base > 0 else 1.0
                    kb = 0 if frac < 0.5 else (1 if frac < 0.95 else 2)
                    pts[s] += (0.6 + 0.8 * (frac if frac < 1.5 else 1.5) + (1.2 if tc > 0 else 0.0)
                               + (0.8 if tc > 0 and frac >= 1.2 else 0.0)) * opp[s].hon(kb)
                pot += amt - bets[s]
                bets[s] = amt
                cur = amt
            elif a == "call":
                if street == "preflop":
                    if L == 0:
                        limp += 1
                        role[s] = ("l", 0, False)
                    else:
                        callers += 1
                        role[s] = ("c", L, tc >= 800)
                else:
                    cp[s] += 0.3
                pot += amt
                bets[s] += amt
            elif a == "check":
                if street == "preflop":
                    role.setdefault(s, ("l", 0, False))
                else:
                    self.chk.add(s)
        return L, lastr, limp, callers, role, pts, cp

    def _range_t(self, s, role):
        """Fraction of starting hands this seat can hold given its preflop action.

        Starts from how often the seat takes that action and is pulled toward the hands it has actually
        shown down after the same kind of action (opens, re-raises, calls and shoves are kept apart)."""
        o = self.opp[s]
        r = role.get(s)
        if r is None:
            return 1.0
        kind = r[0]
        lvl = r[1]
        jam = r[2]
        sdn = o.sdn
        sds = o.sds
        if kind == "r":
            cx = r[3]
            if lvl == 1:
                t = (o.pf() * 3.0 + 2.0 * sds[0]) / (3.0 + sdn[0])
                if not jam:
                    # Early seats open tighter than the seat's average, late seats wider.
                    t *= (1.0, 1.6, 1.8, 1.3, 1.0, 0.8, 0.7, 0.6)[(self.btn + 2 - s) % self.n % 8]
            elif lvl == 2:
                tf = o.t3c(cx)
                t = (tf * 3.0 + 2.0 * o.sd1s[cx]) / (3.0 + o.sd1n[cx])
            else:
                # A 4-bet or later comes from the range the seat already raised with: its opening range
                # (odd levels) or its 3-bet range (even levels), times how often it raises again.
                base = o.pf() if lvl % 2 else o.t3c(0)
                t = base * o.t4c(cx)
                if lvl >= 5:
                    t *= o.t4c(cx)
                if t < 0.012:
                    t = 0.012
            if jam:
                tj = ((o.sh() if lvl == 1 else t) * 3.0 + 2.0 * o.sd4s[cx]) / (3.0 + o.sd4n[cx])
                t = tj if lvl == 1 else (tj if tj < t else t)
        elif kind == "c":
            if jam:
                tf = min(o.vp(), o.cbig() * 0.5)
                if tf < 0.04:
                    tf = 0.04
                t = (tf * 3.0 + 2.0 * sds[3]) / (3.0 + sdn[3])
            elif lvl <= 1:
                t = (o.vp() * 3.0 + 2.0 * sds[2]) / (3.0 + sdn[2])
            else:
                t = max(0.05, o.vp() * 0.35)
        else:
            t = max(o.vp(), 0.5)
        return 1.0 if t > 1.0 else (0.02 if t < 0.02 else t)

    # ------------------------------------------------------------------ decisions
    def _act(self, st, t0):
        legal = st["legal_actions"]
        me = st["seat"]
        n = len(st["stacks"])
        if n != len(self.opp):
            self.opp = [Opp(DEFAULT_PRIOR) for _ in range(n)]
        self.n = n
        self.me = me
        self.btn = st["button"]
        if st["hand_number"] != self.hand:
            self.hand = st["hand_number"]
            self.cache = {}
        elif self.sent:
            self._check_sent(self.hand, st["history"])
        hole = [CARD[x] for x in st["hole_cards"]]
        board = [CARD[x] for x in st["board"]]
        tc = st["to_call"]
        can_raise = "raise" in legal
        lo = st["min_raise_to"]
        hi = st["max_raise_to"]

        def R(to):
            if not can_raise:
                return {"action": "call"} if tc > 0 else {"action": "check"}
            to = int(to)
            if to >= 0.6 * hi:
                to = hi
            if to < lo:
                to = lo
            return {"action": "raise", "amount": to}

        info = self._scan(st)
        if st["street"] == "preflop":
            return self._preflop(st, hole, tc, can_raise, hi, R, info)
        return self._postflop(st, hole, board, tc, can_raise, hi, R, info, t0)

    def _preflop(self, st, hole, tc, can_raise, hi, R, info):
        P = self.P
        L, lastr, limp, callers, role, pts, cp = info
        me = self.me
        n = self.n
        opp = self.opp
        bbv = st["big_blind"]
        pot = st["pot"]
        folded = st["folded"]
        mybet = st["bets"][me]
        total = st["stacks"][me] + mybet
        c = cls(hole[0], hole[1])
        p = PCT[c]
        CALL = {"action": "call"} if tc > 0 else {"action": "check"}
        FOLD = {"action": "check"} if tc == 0 else {"action": "fold"}
        live = [s for s in range(n) if s != me and not folded[s]]

        if L <= 1 and can_raise and tc < 0.3 * total:
            # A seat that calls shoves with almost anything is still in: shove when that is worth more than playing.
            qs = [opp[s].qj() for s in live]
            if qs and max(qs) >= 0.5:
                p0 = 1.0
                for q in qs:
                    p0 *= 1.0 - q
                evs = p0 * pot
                p1s = 0.0
                for q in qs:
                    p1 = q * p0 / (1.0 - q)
                    p1s += p1
                    evs += p1 * (eqr(c, q if q > 0.02 else 0.02) * (2 * total + pot) - total)
                pm = 1.0 - p0 - p1s
                if pm > 0:
                    evs += pm * (eqr(c, max(qs)) * eqr(c, 0.05) * 3 * total - total)
                if evs >= P["shove_ev"] * total:
                    return {"action": "raise", "amount": hi}

        if L == 0:
            if tc == 0:
                if p <= 0.12:
                    return R((3 + limp) * bbv)
                return CALL
            nb = (st["button"] + 2 - me) % n if n > 2 else 1
            th = P["open"][nb if nb < 8 else 7]
            prod = 1.0
            vsum = 0.0
            k = 0
            for i in range(1, nb + 1):
                s = (me + i) % n
                if folded[s]:
                    continue
                v = opp[s].fr()
                prod *= v if v > 0.03 else 0.03
                vsum += 1.0 - v
                k += 1
            if limp:
                for s in live:
                    r = role.get(s)
                    if r is not None and r[0] == "l":
                        v = opp[s].fr()
                        prod *= v if v > 0.03 else 0.03
                        vsum += 1.0 - v
                        k += 1
            if k:
                ratio = (prod / (0.78 ** k)) ** 0.6
                th *= 0.75 if ratio < 0.75 else (1.8 if ratio > 1.8 else ratio)
            if limp:
                th *= 0.9
            elif nb <= 3:
                # Only the blinds (and maybe the button) are left: chance that everyone folds.
                bbseat = (st["button"] + 2) % n
                pf_all = 1.0
                for i in range(1, nb + 1):
                    s = (me + i) % n
                    if not folded[s]:
                        pf_all *= opp[s].bbfold() if s == bbseat else opp[s].fr()
                edge = pf_all - (0.47, 0.52, 0.58)[nb - 1]
                if edge >= 0.0:
                    th = max(th, 0.92)
                elif edge >= -0.07:
                    th = max(th, 0.70)
                elif edge >= -0.14:
                    th = max(th, 0.50)
            if th > 0.92:
                th = 0.92
            if p <= th:
                size = P["open_bb"]
                if k and vsum / k > 0.5:
                    size += 1.5
                return R((size + limp) * bbv)
            return FOLD

        req = tc / float(pot + tc) if tc > 0 else 0.0
        t = self._range_t(lastr, role) if lastr >= 0 and lastr != me else 0.05
        cur = mybet + tc
        # Opponents who have shown real strength this hand: the last raiser, anyone who re-raised, anyone
        # already committed. They are all still to be beaten, so equity is taken against the whole group.
        bets = st["bets"]
        strong = []
        for s in live:
            r = role.get(s)
            if s == lastr or bets[s] >= 600 or (r is not None and r[0] == "r" and r[1] >= 2):
                strong.append(s)
        m = len(strong)
        em = None
        if m >= 2:
            prod = 1.0
            for s in strong:
                prod *= eqr(c, self._range_t(s, role))
            e1 = EQR[c][-1]
            if m <= 3:
                crowd = (EQ3[c] / e1) ** ((m - 1) / 2.0)
            else:
                crowd = EQ3[c] / e1 * (EQ6[c] / EQ3[c]) ** ((m - 3) / 3.0)
            em = prod ** (1.0 / m) * crowd
        if tc >= 0.3 * total or (lastr in role and role[lastr][2]):
            e = em if em is not None else eqr(c, t) - 0.06 * callers
            if e >= req + P["allin_margin"]:
                if e >= 0.62 and can_raise and m <= 1:
                    return {"action": "raise", "amount": hi}
                return CALL
            return FOLD
        if L == 1:
            if eqr(c, t) >= P["tb_eq"] or p <= 0.012:
                return R(3.2 * cur + callers * cur)
            o = opp[lastr]
            if callers == 0 and tc <= 0.06 * total:
                # This opener folds to re-raises: the more often, the wider and more often we re-raise.
                f3 = o.f3()
                if o.f3o >= 4 and f3 >= P["light3"] + 0.12:
                    if p <= 0.85 and random.random() < 0.9:
                        return R(3.0 * cur)
                elif o.f3o >= 3 and f3 >= P["light3"]:
                    if p <= 0.40 and random.random() < 0.75:
                        return R(3.0 * cur)
            if me == (st["button"] + 2) % n and tc <= 0.07 * total and eqr(c, t) >= req + P["bb_def"] + 0.03 * callers:
                return CALL
            cf = P["call_frac"] * (1.6 if req <= 0.26 else 1.0)
            if me == (st["button"] + 1) % n:
                # Small blind: out of position for the whole hand. On 11,000 Sunday hands these calls lost
                # about 49 chips each against 10 for folding, so only the stronger part is kept.
                cf = P["call_frac"] * 0.4
            if p <= min(0.55, cf * t) and tc <= 0.08 * total:
                return CALL
            return FOLD
        if L == 2:
            mine = role.get(me)
            cold = mine is None or mine[0] != "r"
            e = em if em is not None else eqr(c, t)
            if e >= (0.66 if cold else P["f3_raise"]) or p <= 0.007:
                return R(2.3 * cur)
            if e >= req + (0.12 if cold else P["f3_call"]) and tc <= 0.15 * total:
                return CALL
            return FOLD
        e = em if em is not None else eqr(c, t) - 0.06 * callers
        if e >= P["war_eq"] or p <= 0.0025:
            return {"action": "raise", "amount": hi} if can_raise else CALL
        if e >= req + 0.06:
            return CALL
        return FOLD

    def _postflop(self, st, hole, board, tc, can_raise, hi, R, info, t0):
        P = self.P
        L, lastr, limp, callers, role, pts, cp = info
        me = self.me
        n = self.n
        opp = self.opp
        pot = st["pot"]
        folded = st["folded"]
        mybet = st["bets"][me]
        stack = st["stacks"][me]
        CALL = {"action": "call"} if tc > 0 else {"action": "check"}
        FOLD = {"action": "check"} if tc == 0 else {"action": "fold"}
        live = [s for s in range(n) if s != me and not folded[s]]
        if not live:
            return CALL
        od = []
        minftb = 1.0
        prodftb = 1.0
        station = False
        for s in live:
            o = opp[s]
            t = self._range_t(s, role)
            af = o.af()
            m = 0.30 / af
            m = 0.5 if m < 0.5 else (1.6 if m > 1.6 else m)
            f = o.ftb()
            mc = f / 0.42
            if mc > 1.5:
                mc = 1.5
            k = 1.0 + pts[s] * m + cp[s] * mc
            if k > 6.0:
                k = 6.0
            od.append((max(8, int(t * NCOMB)), int(k * 4 + 0.5) / 4.0))
            if f < minftb:
                minftb = f
            prodftb *= f
            if o.fb >= 8 and f < 0.15:
                station = True
        if self.used < 5.0:
            # Think longer the more chips are at stake: up to 6x in the biggest pots (limit is 25 ms).
            stake = pot + tc
            budget = P["mc_ms"] * self.scale * (6.0 if stake >= 1200 else (4.0 if stake >= 500 else (2.0 if stake >= 200 else 1.0)))
            if budget < 0.25:
                budget = 0.25
        elif self.used < 7.5:
            budget = 1.0
        else:
            budget = 0.3
        e = self._equity(hole, board, od, t0 + budget / 1000.0)
        no = len(live)
        street = st["street"]

        if tc == 0 and can_raise and no == 1:
            # Heads-up: compare betting each size with checking, using this opponent's fold rate by size.
            s1 = live[0]
            o = opp[s1]
            si = 1 if street == "flop" else (2 if street == "turn" else 3)
            button = st["button"]
            ip = ((me - button - 1) % n) > ((s1 - button - 1) % n)
            if si == 3:
                rz = 1.0
            else:
                rz = 1.0 - (0.6 if si == 1 else 0.3) * o.af()
                if not ip:
                    rz -= 0.05
            chk = e * rz
            spr = stack / float(pot) if pot > 0 else 1.0
            stg = 1 if (pts[s1] > 0 or cp[s1] > 0) else 0
            tfb = self.tfb
            tfd = self.tfd
            # fold_at pools every bet a seat has faced, but position decides a lot. On 10,500 real heads-up
            # flop and turn bets (data/hands r002-r036) a seat that acts after the bettor folded 37% of
            # the time where fold_at said 52%; the same gap shows in r002-r023 and in r024-r036. So when
            # we bet first on the flop or turn, the fold chance is scaled by 'oop_fold' (per size bucket).
            # With 'oop_learn' that field number is only the starting point: the scale moves toward
            # real folds / predicted folds seen at this table and from this seat in the same spot.
            # 'oop_fold': [1, 1, 1, 1] with 'oop_learn': 0 gives the uncorrected numbers.
            fm = (1.0, 1.0, 1.0, 1.0)
            if not ip and si < 3:
                # Medium hands bet first into a big or re-raised pot lost 220-400 chips a bet on real hands
                # (r018-r036); bluffs and value bets there did not. 'oop_med_pot': 0 switches this off.
                mp = P.get("oop_med_pot", 0)
                if mp and 0.35 <= e < 0.6 and (pot >= mp or L >= 2):
                    return CALL
                fm = P.get("oop_fold") or fm
                if P.get("oop_learn"):
                    base = fm[1]
                    tr = (self.tipd + base * 8.0) / (self.tipp + 8.0)
                    r = (o.ipd + tr * 4.0) / (o.ipp + 4.0) / base
                    r = 0.6 if r < 0.6 else (1.4 if r > 1.4 else r)
                    fm = [x * r for x in fm]
            fcm = 1.0
            if stg and spr < P.get("commit_spr", 0.0) and (si < 3 or spr < 0.5):
                fcm = P.get("commit_mult", 1.0)
            if e >= 0.5:
                cands = [(0.4, 0), (0.7, 1), (1.1, 2), (2.0, 3)]
            else:
                cands = [(0.4, 0), (0.7, 1), (1.1, 2)]
            if spr > 2.6 and e >= 0.62:
                # Shoving several times the pot only against a seat that has itself shown it calls such bets.
                ofb = o.fbk[stg]
                nall = ofb[0] + ofb[1] + ofb[2] + ofb[3]
                nob = o.fbk[0][3] + o.fbk[1][3]
                if ((nob >= 4 and o.fdk[0][3] + o.fdk[1][3] <= 0.5 * nob)
                        or (nall >= 10 and sum(o.fdk[stg]) < 0.12 * nall)):
                    cands.append((spr, 3))
            best = 0.0
            bfrac = 0.0
            for frac, kb in cands:
                if frac > spr:
                    frac = spr
                f = o.fold_at(kb, stg, tfb, tfd) * fm[kb] * fcm
                if frac > 3.0 and f > 0.15:
                    f = f + 0.10 if f < 0.85 else 0.95
                wc = (e - f) / (1.0 - f) if e > f else 0.0
                if si < 3:
                    fl = e * (0.55 if si == 1 else 0.4)
                    if wc < fl:
                        wc = fl
                g = f + (1.0 - f) * (wc * (1.0 + 2.0 * frac) - frac) - chk
                if g > best:
                    best = g
                    bfrac = frac
            if bfrac:
                if e >= 0.5:
                    if best > P["bet_edge"]:
                        return R(mybet + bfrac * pot)
                elif best > P["bluff_edge"] and (lastr == me or s1 in self.chk or o.fb >= 6):
                    if random.random() < P["cbet_freq"]:
                        return R(mybet + bfrac * pot)
            return CALL

        if tc == 0:
            if not can_raise:
                return CALL
            vt = P["value"] if no == 1 else 1.0 / (no + 1) + 0.10 + 0.04 * (no - 1)
            if station and no == 1:
                vt = 0.54
            if e >= vt:
                frac = P["bet_big"] if e >= 0.85 else P["bet_med"]
                if station:
                    if e >= 0.68:
                        return {"action": "raise", "amount": hi}
                    frac = 1.3
                elif minftb < 0.3:
                    frac *= 1.3
                return R(mybet + frac * pot)
            b = P["cbet_size"] * pot
            need = b / (pot + b) + P["bluff_edge"]
            if no == 1:
                o = opp[live[0]]
                f = o.ftb()
                pfa = lastr == me and street == "flop"
                if f >= need and (pfa or o.fb >= 6) and random.random() < P["cbet_freq"]:
                    return R(mybet + b)
            elif no == 2 and prodftb >= need + 0.05 and lastr == me and street == "flop":
                if random.random() < 0.5:
                    return R(mybet + b)
            return CALL

        req = tc / float(pot + tc)
        allin = tc >= stack
        rt = P["raise"] - 0.08 * (no - 1)
        if rt < 0.6:
            rt = 0.6
        if no == 1 and can_raise and not allin and e >= P["raise_min"]:
            # Heads-up value raise: pick the size that earns most given how often this opponent folds to it.
            o = opp[live[0]]
            if station and e >= 0.7:
                return {"action": "raise", "amount": hi}
            tfb = self.tfb
            tfd = self.tfd
            base = float(pot + tc)
            sprr = (stack - tc) / base
            cands = [(0.6, 1), (1.0, 2), (1.8, 3)]
            nob = o.fbk[0][3] + o.fbk[1][3]
            if sprr > 2.6 and nob >= 4 and o.fdk[0][3] + o.fdk[1][3] <= 0.5 * nob:
                cands.append((sprr, 3))
            best = 0.0
            br = 0.0
            for frac, kb in cands:
                if frac > sprr:
                    frac = sprr
                f = o.fold_at(kb, 1, tfb, tfd)
                if frac > 3.0 and f > 0.15:
                    f = f + 0.10 if f < 0.85 else 0.95
                g = frac * (2.0 * e - 1.0 - f)
                if g > best:
                    best = g
                    br = frac
            if br and best > P["raise_edge"]:
                return R(mybet + tc + br * base)
        elif e >= rt and can_raise and not allin:
            if station and e >= 0.7:
                return {"action": "raise", "amount": hi}
            return R(mybet + tc + 0.75 * (pot + tc))
        margin = P["call_margin"]
        if street != "river" and not allin:
            margin += P["early_margin"]
        if e >= req + margin:
            return CALL
        return FOLD

    # ------------------------------------------------------------------ Monte Carlo equity
    def _equity(self, hole, board, od, deadline):
        """P(win) against every live opponent. od = [(combos in range, strength bias k), ...].

        Each opponent's hand is drawn from the top of the preflop ordering, and when k > 1 it is the
        best of k such draws on the current board, which skews the range toward made hands.
        """
        key = (len(board), tuple(od))
        c = self.cache.get(key)
        if c is None:
            c = [0.0, 0]
            self.cache[key] = c
        if c[1] >= 2000:
            return c[0] / c[1]
        used0 = 0
        for x in hole:
            used0 |= 1 << x
        for x in board:
            used0 |= 1 << x
        deck = [x for x in range(52) if not (used0 >> x) & 1]
        nd = len(deck)
        need = 5 - len(board)
        rnd = random.random
        COMB = COMBOS
        NC = NCOMB
        RBIT = RB
        POPC = POP
        h0, h1 = hole
        # Evaluator state of the board, extended per sample by the cards still to come.
        bpre = prep(board)
        B1, B2, B3, B4 = bpre[0], bpre[1], bpre[2], bpre[3]
        S = [0, 0, 0, 0]
        for x in board:
            S[x & 3] |= RBIT[x]
        if not need:
            fpre = bpre
            mv = ev2(bpre, h0, h1)
        w = 0.0
        cnt = 0
        while True:
            for _ in range(2):
                used = used0
                oh = []
                for ntop, k in od:
                    kk = int(k)
                    if k > kk and rnd() < k - kk:
                        kk += 1
                    nt = NC if (ntop < NC and rnd() < 0.12) else ntop
                    ba = bb = -1
                    bv = -1
                    for _j in range(kk):
                        tries = 0
                        while True:
                            a, b = COMB[int(rnd() * nt)]
                            if not ((used >> a) & 1 or (used >> b) & 1):
                                break
                            tries += 1
                            if tries > 5:
                                nt = NC
                        if kk == 1:
                            ba = a
                            bb = b
                            break
                        v = ev2(bpre, a, b)
                        if v > bv:
                            bv = v
                            ba = a
                            bb = b
                    used |= (1 << ba) | (1 << bb)
                    oh.append(ba)
                    oh.append(bb)
                    oh.append(bv)
                if need:
                    m1 = B1
                    m2 = B2
                    m3 = B3
                    m4 = B4
                    s0, s1, s2, s3 = S
                    m = need
                    while m:
                        x = deck[int(rnd() * nd)]
                        if (used >> x) & 1:
                            continue
                        used |= 1 << x
                        b = RBIT[x]
                        sx = x & 3
                        if sx == 0:
                            s0 |= b
                        elif sx == 1:
                            s1 |= b
                        elif sx == 2:
                            s2 |= b
                        else:
                            s3 |= b
                        m4 |= m3 & b
                        m3 |= m2 & b
                        m2 |= m1 & b
                        m1 |= b
                        m -= 1
                    if POPC[s0] >= 3:
                        fpre = (m1, m2, m3, m4, 0, s0)
                    elif POPC[s1] >= 3:
                        fpre = (m1, m2, m3, m4, 1, s1)
                    elif POPC[s2] >= 3:
                        fpre = (m1, m2, m3, m4, 2, s2)
                    elif POPC[s3] >= 3:
                        fpre = (m1, m2, m3, m4, 3, s3)
                    else:
                        fpre = (m1, m2, m3, m4, -1, 0)
                    mv = ev2(fpre, h0, h1)
                lose = False
                ties = 1
                for i in range(0, len(oh), 3):
                    ov = oh[i + 2]
                    if need or ov < 0:
                        # On the river a best-of-k draw was already scored on the full board.
                        ov = ev2(fpre, oh[i], oh[i + 1])
                    if ov > mv:
                        lose = True
                        break
                    if ov == mv:
                        ties += 1
                if not lose:
                    w += 1.0 / ties
                cnt += 1
            if cnt >= 2000 or _pc() >= deadline:
                break
        c[0] += w
        c[1] += cnt
        return c[0] / c[1]


# Park the big import-time tables outside the collector's reach so a collection can't stall a decision.
# The bot creates no reference cycles, so automatic collection is switched off and a cheap manual pass runs
# between hands instead (see on_hand_end).
try:
    gc.collect()
    gc.freeze()
    gc.disable()
except Exception:
    pass
