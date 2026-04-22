import numpy as np

# FMO Hamiltonian from Adolphs & Renger (cm^-1)
H = np.array([
    [280, -106,   8,  -5,   6,  -8,  -4],
    [-106, 420,  28,   6,   2,  13,   1],
    [  8,  28,   0, -53,  29, -70,  46],
    [ -5,   6, -53, 175, -70, -19, -54],
    [  6,   2,  29, -70, 320,  40, -34],
    [ -8,  13, -70, -19,  40, 360,  32],
    [ -4,   1,  46, -54, -34,  32, 260]
], dtype=float)

N = 7
sink_idx = 2  # FMO site 3
Gamma = 1.0   # Sink rate

def solve_yield(gamma_deph):
    H_eff = H - 1j * np.zeros_like(H)
    H_eff[sink_idx, sink_idx] -= 1j * Gamma

    I = np.eye(N)
    L_coh = -1j * (np.kron(H_eff, I) - np.kron(I, H_eff.conj()))
    
    L_deph = np.zeros((N**2, N**2))
    for i in range(N):
        for j in range(N):
            idx = i*N + j
            if i != j:
                L_deph[idx, idx] = -gamma_deph
                k_decay = 1.0
    L = L_coh + L_deph - k_decay * np.eye(N**2)
    rho0 = np.zeros((N, N))
    rho0[0, 0] = 1.0  # Excited at site 1 (index 0)
    rho0_vec = rho0.flatten()
    
    # We solve L * x = -rho0_vec
    x = np.linalg.solve(L, -rho0_vec)
    
    # x is the integral of rho(t) from 0 to inf
    rho_int = x.reshape((N, N))
    
    return 2 * Gamma * np.real(rho_int[sink_idx, sink_idx])

for g in [0, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0, 100000.0]:
    yld = solve_yield(g)
    print(f"gamma={g:6.1f} -> yield={yld:.4f}")
