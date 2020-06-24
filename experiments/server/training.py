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
from stable_baselines.deepq import DQN, MlpPolicy, LnCnnPolicy, LnMlpPolicy
from stable_baselines.common.env_checker import check_env
from stable_baselines.deepq.policies import DQNPolicy
from stable_baselines.common.policies import CnnLnLstmPolicy
from stable_baselines.common.buffers import ReplayBuffer, PrioritizedReplayBuffer
from stable_baselines.common.policies import MlpPolicy
from stable_baselines.common import make_vec_env
from stable_baselines import A2C

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
    parser.add_argument("-gui", action="store_true", default=True, help="Run with visualization on SUMO.\n"),
    parser.add_argument("-plot", action="store_true", default=True, help="Plot graphs.\n"),
    parser.add_argument("-sim_steps", dest="sim_steps", type =int, default=48335 , help="Max simulation steps.\n"),
    parser.add_argument("-trains", dest="trains", type =int, default=30, help="Max trainings.\n"),
    parser.add_argument("-pun", dest="pun", type =float, default=1.0, help="Forced ToC messages punishment factor.\n"),
    parser.add_argument("-zip", dest="zip", type=str,
                        default='dqn_sample.zip',
                        help="Load the dqn model zip file.\n")


    # parser.add_argument("-runs", dest="runs", type=int, default=1, help="Number of runs.\n")

    args = parser.parse_args()
    experiment_time = str(datetime.now()).split('.')[0]

    # data folder for every experiment
    # path = os.getcwd() + "/outputs/" + datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.getcwd() + "/outputs/trainings/" + args.zip+"_"+datetime.now().strftime("%Y%m%d-%H%M%S")


    try:
        if not os.path.exists(path):
            os.mkdir(path)
    except OSError:
        print ("Creation of the directory %s failed" % path)
    else:
        print ("Successfully created the directory %s" % path)
    
    # save args to file
    f= open(path+'/argsfile.txt',"w+")
    for arg in vars(args):
        f.write(arg + ' ' + str(getattr(args, arg)) + '\n')
    f.close()   




    env = gym.make('tor_distribution:tor-v0',
                    cfg_file=args.cfg,
                    net_file=args.network,
                    route_file=args.route,
                    vTypes_files=args.vTypes,
                    use_gui=args.gui,
                    sim_steps = args.sim_steps,
                    trains = args.trains,
                    plot = args.plot,
                    delay=100,
                    forced_toc_pun=args.pun,
                    data_path = path)


    # It will check your custom environment and output additional warnings if needed
    # check_env(env)

    # initialization of the DQN training model
    model = DQN(
        env=env,
        policy=LnMlpPolicy,
        gamma=0.99,
        prioritized_replay=True,
        learning_rate=1e-3,
        buffer_size=50000,
        exploration_fraction=0.1,
        exploration_final_eps=0.02,
        verbose = 2,
        tensorboard_log="./../../../../media/ml_share/noul_ar/dqn_tensorboard/"
    )
    # model = A2C(MlpPolicy, env,
    #             gamma=0.99,
    #             learning_rate=1e-3, 
    #             verbose=2,
    #             tensorboard_log="./a2c_tensorboard/")

    #execute the training
    print()
    print("Start the training for", args.trains, "episodes and simulation steps " +str(args.sim_steps) + "\n")
    model.learn(total_timesteps=(args.trains*args.sim_steps))

    # save, delete and restore model
    print("Save the model " +str(args.zip)+ " \n")
    model.save(args.zip)

    env.close()
    print()
    elapsed_time = time.time()- start
    print("Duration of the training experiment =", time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))


if __name__ == '__main__':
    main()
