#include "utils.h"
#include "auxiliary.h"


// Equation (9) in "3D Gaussian Splatting as Markov Chain Monte Carlo"
__global__ void compute_relocation(
    int P, 
    float* opacity_old, 
    float* scale_old, 
    int* N, 
    float* binoms, 
    int n_max, 
    float* opacity_new, 
    float* scale_new) 
{
    int idx = threadIdx.x + blockIdx.x * blockDim.x;
    if (idx >= P) return;
    
    int N_idx = N[idx];
    float denom_sum = 0.0f;

    // compute new opacity
    opacity_new[idx] = 1.0f - powf(1.0f - opacity_old[idx], 1.0f / N_idx);