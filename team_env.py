import gymnasium as gym
from gymnasium import spaces
import numpy as np

class CollaborativeTeamEnv(gym.Env):
    """
    Custom Environment for the Synchrony-Aware AI Agent.
    """
    def __init__(self):
        super(CollaborativeTeamEnv, self).__init__()
        
        # ACTION SPACE: 27 discrete combinations
        # (3 Timing options x 3 Detail Levels x 3 Styles)
        self.action_space = spaces.Discrete(27)
        
        # OBSERVATION SPACE (State): 22-dimensional vector
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(22,), dtype=np.float32
        )
        
        self.current_step = 0
        self.max_steps = 120  # Represents a 20-minute task with 10-second updates
        self.current_synchrony = 0.5

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.current_synchrony = 0.5 
        
        initial_state = np.random.uniform(low=-0.5, high=0.5, size=(22,)).astype(np.float32)
        return initial_state, {}

    def step(self, action):
        self.current_step += 1
        
        # Simulate the team's response to the agent's intervention
        impact = np.random.uniform(-0.1, 0.2)
        self.current_synchrony = np.clip(self.current_synchrony + impact, 0.0, 1.0)
        
        # REWARD FUNCTION: The agent gets points for maintaining high synchrony
        reward = self.current_synchrony
        
        next_state = np.random.uniform(low=-0.5, high=0.5, size=(22,)).astype(np.float32)
        
        terminated = self.current_step >= self.max_steps
        truncated = False
        
        return next_state, reward, terminated, truncated, {}