def calculate_swarm_velocity(agents, area):
    speeds = []
    for a in agents:
        speed = a.power / area
        speeds.append(speed)
    return sum(speeds)
