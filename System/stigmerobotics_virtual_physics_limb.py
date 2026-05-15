import math
from typing import Dict, Any

# Real-world data approximating a mid-size robotic arm link (e.g., UR5 lower arm)
PHYSICS_PARAMS = {
    "mass_kg": 3.8,
    "length_m": 0.425,
    "gravity_m_s2": 9.81,
    "damping_nms_rad": 0.5,
    "restitution_coeff": 0.5, # Energy kept after collision
    "joint_limit_min_rad": -math.pi / 2.0, # Straight up
    "joint_limit_max_rad": math.pi / 2.0   # Straight down
}

def simulate_limb_step(current_state: Dict[str, float], torque_nm: float, duration_ms: float) -> tuple[Dict[str, float], bool]:
    """
    Advances a 1-DOF robotic link (pendulum) using semi-implicit Euler integration.
    Returns (new_state, collision_occurred).
    """
    m = PHYSICS_PARAMS["mass_kg"]
    L = PHYSICS_PARAMS["length_m"]
    g = PHYSICS_PARAMS["gravity_m_s2"]
    b = PHYSICS_PARAMS["damping_nms_rad"]
    
    # Moment of inertia for a rod pivoted at one end: I = 1/3 * m * L^2
    I = (1.0 / 3.0) * m * (L ** 2)
    
    theta = current_state.get("theta_rad", 0.0)
    omega = current_state.get("omega_rad_s", 0.0)
    
    dt = duration_ms / 1000.0
    steps = int(max(1, dt // 0.001)) # 1ms micro-steps for stability
    dt_step = dt / steps
    
    collision = False
    
    for _ in range(steps):
        # Gravity torque: acts downwards. If theta=0 is horizontal right, gravity torque is -m*g*(L/2)*cos(theta)
        # Let's say theta=0 is straight down. Gravity torque = -m*g*(L/2)*sin(theta)
        gravity_torque = -m * g * (L / 2.0) * math.sin(theta)
        
        # alpha = (tau + gravity_torque - damping*omega) / I
        alpha = (torque_nm + gravity_torque - b * omega) / I
        
        # Semi-implicit Euler
        omega += alpha * dt_step
        theta += omega * dt_step
        
        # Collision with joint limits
        if theta < PHYSICS_PARAMS["joint_limit_min_rad"]:
            theta = PHYSICS_PARAMS["joint_limit_min_rad"]
            omega = -omega * PHYSICS_PARAMS["restitution_coeff"]
            collision = True
        elif theta > PHYSICS_PARAMS["joint_limit_max_rad"]:
            theta = PHYSICS_PARAMS["joint_limit_max_rad"]
            omega = -omega * PHYSICS_PARAMS["restitution_coeff"]
            collision = True

    return {"theta_rad": theta, "omega_rad_s": omega}, collision
