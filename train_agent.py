from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from team_env import CollaborativeTeamEnv

# 1. Initialize your custom environment
env = CollaborativeTeamEnv()

# Verify the environment follows standard RL rules
check_env(env, warn=True)

# 2. Build the PPO Model architecture
# Using a 3-layer Multi-Layer Perceptron
policy_kwargs = dict(net_arch=dict(pi=[64, 128, 64], vf=[64, 128, 64]))

model = PPO("MlpPolicy", env, policy_kwargs=policy_kwargs, verbose=1)

print("Starting Phase 1 Training in Simulated Environment...")

# 3. Train for 100,000 steps
model.learn(total_timesteps=100000)

# 4. Save the trained brain
model.save("ppo_synchrony_agent")
print("Agent successfully trained and saved!")