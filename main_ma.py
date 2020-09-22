import ray
from ray.rllib.agents.a3c.a3c import A3CTrainer
from ray.rllib.agents.a3c.a3c_tf_policy import A3CTFPolicy
from ray.tune.registry import register_env
from ray.rllib.agents.dqn import DQNTrainer
from ray.rllib.agents.dqn.dqn_tf_policy import DQNTFPolicy
from ray.rllib.examples.policy.random_policy import RandomPolicy
from ray.tune.logger import pretty_print
from ray import tune
from ray.rllib.agents.trainer_template import build_trainer
from ray.rllib.evaluation.postprocessing import discount
from ray.rllib.policy.tf_policy_template import build_tf_policy
from ray.rllib.utils.framework import try_import_tf
from myDQNTFPolicy import RandomPolicy, myDQNTFPolicy
import subprocess
from ray.rllib.examples.models.custom_loss_model import CustomLossModel
from ray.rllib.agents.callbacks import DefaultCallbacks
from ray.rllib.models import ModelCatalog
from time import strftime
from copy import deepcopy
import os
# 0 = all messages are logged (default behavior)
# 1 = INFO messages are not printed
# 2 = INFO and WARNING messages are not printed
# 3 = INFO, WARNING, and ERROR messages are not printed
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # temporaly disable gpu
os.environ["CUDA_VISIBLE_DEVICES"] = "0" # see gpu

import gym
gym.logger.set_level(40)
import numpy as np
import warnings
warnings.filterwarnings('ignore',category=FutureWarning)
import tensorflow as tf
from datetime import datetime
import random
from collections import deque
from tor_distribution.envs.tor_env import TorEnv
import argparse
import sys
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare the environment variable 'SUMO_HOME'")
import pandas as pd
from gym import spaces
import numpy as np
import traci
import time
import os
from datetime import datetime
from callbacks import MyCallbacks
import tempfile
from  ray.tune.logger import UnifiedLogger

DEFAULT_RESULTS_DIR = os.getcwd() + '/outputs/ray_results/'
# DEFAULT_RESULTS_DIR = '/media/ml_share/noul_ar/outputs/ray_results/'


def main():
    start = time.time()
    if tf.test.gpu_device_name():
        print('Default GPU Device: {}'.format(tf.test.gpu_device_name()))
    else:
        print("Please install GPU version of TF or use the GPU")

    tf.compat.v1.logging.set_verbosity( tf.compat.v1.logging.ERROR)

    print('tensorflow version', tf.__version__)
    print('gym version', gym.__version__)
    parser = argparse.ArgumentParser(description='Process some entries.')

    parser.add_argument("-cfg", dest="cfg", type=str,
                        default='scenario/sumo.cfg',
                        help="Network definition xml file.\n")
    parser.add_argument("-net", dest="network", type=str,
                        default='scenario/UC5_1.net.xml',
                        help="Network definition xml file.\n")
    parser.add_argument("-route", dest="route", type=str,
                        default='scenario/routes_trafficMix_0_trafficDemand_1_driverBehaviour_OS_seed_0.xml',
                        help="Route definition xml file.\n")
    parser.add_argument("-vTypes", dest="vTypes", type=str, nargs='*',
                        default=['scenario/vTypesCAVToC_OS.add.xml','scenario/vTypesCVToC_OS.add.xml','scenario/vTypesLV_OS.add.xml'],
                        help="Route definition xml file.\n")
    parser.add_argument("-sim_steps", dest="sim_steps", type =int, default=48335 , help="Max simulation steps.\n"),
    parser.add_argument("-trains", dest="trains", type =int, default=30, help="Max trainings.\n"),
    parser.add_argument("-pun", dest="pun", type =float, default=1.0, help="Forced ToC messages punishment factor.\n"),
    parser.add_argument("-zip", dest="zip", type=str,
                        default='dqn_sample.zip',
                        help="Load the dqn model zip file.\n")
    parser.add_argument("-mode", dest="mode", type=str,
                        default='train',
                        help="Train or Eval\n")
    parser.add_argument("-simulations", dest="simulations", type=int,
                        default=10, help="Number of simulation examples.\n"),


    args = parser.parse_args()
    experiment_time = str(datetime.now()).split('.')[0]

    delay = 0
    envName = "tor-v0"
    eval_path = ""
  
    # data folder for every experiment
    # path = os.getcwd() + "/outputs/" + eval_path+"/"+ datetime.now().strftime("%Y%m%d-%H%M%S")
    # path = os.getcwd() + "/outputs/trainings/" + args.zip+"_"+datetime.now().strftime("%Y%m%d-%H%M%S")

    cells_number = 14
    agents = 3
    cellsPerAgent = int((cells_number-2)/agents)
    if args.mode == 'train':
            # Register the model and environment
            register_env(envName, lambda _: TorEnv(
                            cfg_file=args.cfg,
                            net_file=args.network,
                            route_file=args.route,
                            vTypes_files=args.vTypes,
                            use_gui=False,
                            sim_steps=args.sim_steps,
                            trains = args.trains,
                            plot = False,
                            delay=delay,
                            agents=agents))
            
            try:
                do_training(envName, args.sim_steps, args.trains,agents)
            except AssertionError as error:
                print(error)
                print("Problem on training")

    elif args.mode == 'eval':
        print("Let's test")
        rollout(DEFAULT_RESULTS_DIR+eval_path,
                envName, args.sim_steps, args.simulations, eval_path[0:24],agents)

def policy_mapping_fn(agent_id):
    # if agent_id == 0:
    #     return "dqn_policy"
    # else:
    #     return "mydqn_policy"
    return "dqn_policy"


def do_training(envName, sim_steps, trains, agents):
    """Train policies using the DQN algorithm in RLlib."""

    cells_number = 14
    cellsPerAgent = int((cells_number-2)/agents)

    obs_space = spaces.Box(low=-100000, high=100000,
                           shape=(4, int(cellsPerAgent+2)), dtype=np.int)
    act_space = spaces.Discrete(cellsPerAgent+1)

    policies = {
        'dqn_policy': (DQNTFPolicy, obs_space, act_space, {}),
        "mydqn_policy": (DQNTFPolicy, obs_space, act_space, {}),
    }

    ModelCatalog.register_custom_model("custom_loss", CustomLossModel)

    n_cpus = 0
    labels = n_cpus
    # policies_to_train = ['dqn_policy']

    
    #ray.init(num_cpus=n_cpus + 1, memory=6000 * 1024 * 1024,object_store_memory=3000 * 1024 * 1024)
    # Back to default ray initialization
    ray.init()

    myConfig = {

        # Mutli Agent Configs
        "multiagent": {
            # "model": {
            #     "custom_model": "custom_loss",
            # #     "use_lstm": True,
            # #     "lstm_use_prev_action_reward": True,
            # },
            "policies": policies,
            "policy_mapping_fn": policy_mapping_fn,
            # "policies_to_train": policies_to_train
        },

        # DQN params 
        "lr": 0.0005,
        "target_network_update_freq": 100,
        "buffer_size": 300000,
        # === Exploration Settings ===
        "exploration_config": {
            # The Exploration class to use.
            "type": "EpsilonGreedy",
            # Config for the Exploration class' constructor:
            "initial_epsilon": 1.0,
            "final_epsilon": 0.02,
            # Timesteps over which to anneal epsilon.
            "epsilon_timesteps": 0.1 * sim_steps * trains,

            # For soft_q, use:
            # "exploration_config" = {
            #   "type": "SoftQ"
            #   "temperature": [float, e.g. 1.0]
            # }
        },

        # Train-Sim Params
        'timesteps_per_iteration':sim_steps,
        "framework": "tfe",
        'eager_tracing': True,
        "num_workers": n_cpus,
        "callbacks": MyCallbacks,
    }
    timestr = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    logdir_prefix = "{}__{}".format('DQN',timestr)

    def default_logger_creator(config):
        """Creates a Unified logger with a default logdir prefix
        containing the agent name and the env id
        """
        if not os.path.exists(DEFAULT_RESULTS_DIR):
            os.makedirs(DEFAULT_RESULTS_DIR)
        logdir = tempfile.mkdtemp(
            prefix=logdir_prefix, dir=DEFAULT_RESULTS_DIR)
        return UnifiedLogger(config, logdir, loggers=None)


    trainer = DQNTrainer(env=envName, config=myConfig,
                         logger_creator=default_logger_creator)
    # if logger_creator is None:
    #     timestr = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    #     logdir_prefix = "{}_{}_{}".format(self._name, self._env_id,
    #                                       timestr)
    #     logger_creator = default_logger_creator()

    for i in range(trains):
        print(f'== Training Iteration {i+1}==')
        print(pretty_print(trainer.train()))
        checkpoint = trainer.save()
        print(f'\nCheckpoint saved at {checkpoint}\n')

    try:
        TorEnv.close(TorEnv)
    except:
        pass
    ray.shutdown()


def rollout(checkpoint_path, envName, sim_steps, simulations,eval_path, agents):
    subprocess.call([
        sys.executable,
        './rollout.py', checkpoint_path,
        '--env', envName,
        '--steps', str(sim_steps),
        '--run', 'DQN',
        '--no-render',
        '-sim_steps', str(sim_steps),
        '-simulations', str(simulations),
        '-eval_path',eval_path,
        '-agents', str(agents)
    ])

if __name__ == '__main__':
    main()