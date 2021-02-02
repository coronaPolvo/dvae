from cleverhans.utils_tf import model_eval
from cleverhans.attacks import FastGradientMethod
from cleverhans_tutorials.tutorial_models import *
from cleverhans.attacks import CarliniWagnerL2
from .cnn_models import model_a, model_b, model_c, model_d, model_e, model_f
import os
import math
import argparse
import numpy as np
from tensorflow.examples.tutorials.mnist import input_data

parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=int, default=1)  ###1:mnist; 2:fmnist
parser.add_argument('--cnn_model', type=int, default=1)
parser.add_argument('--attack_method', type=int, default=3)  ### 1:fgsm; 2:rand fgsm 3:CW
parser.add_argument('--epsilon', type=float, default=0.25)  ###for cw: 0.2 without feed; 0.3 with feed
parser.add_argument('--cnn-epochs', type=int, default=20)
args = parser.parse_args()

if args.dataset == 1:
    data = input_data.read_data_sets('../data/mnist', validation_size=0)
    base_savedir = 'mnist/'
elif args.dataset == 2:
    data = input_data.read_data_sets('../data/fashion', validation_size=0)
    base_savedir = 'fmnist/'


def to_categorical(y, num_classes=None):
    y = np.array(y, dtype='int').ravel()
    n = y.shape[0]
    categorical = np.zeros((n, num_classes))
    categorical[np.arange(n), y] = 1
    return categorical


X_train = data.train.images
X_train = np.reshape(X_train, (60000, 28, 28, 1))
Y_train = data.train.labels
Y_train = to_categorical(Y_train, num_classes=10)
print(args)

cnn_dir = '../cnn_models/' + base_savedir + 'CNN_model_{}/'.format(args.cnn_model, args.cnn_epochs)
batch_size = 128
config_args = {}
x = tf.placeholder(tf.float32, shape=(None, 28, 28, 1))
y = tf.placeholder(tf.float32, shape=(None, 10))
sess = tf.Session(config=tf.ConfigProto(**config_args))

if args.cnn_model == 1:
    model = model_a()
elif args.cnn_model == 2:
    model = model_b()
elif args.cnn_model == 3:
    model = model_c()
elif args.cnn_model == 4:
    model = model_d()
preds = model.get_probs(x)

saver = tf.train.Saver()
with tf.Session() as sess:
    saver.restore(sess, cnn_dir + "model.ckpt")
    print("Model restored.")

    if args.attack_method == 1:
        attack_params = {'eps': args.epsilon, 'clip_min': 0., 'clip_max': 1.}
        attack_obj = FastGradientMethod(model, sess=sess)
        savedir = base_savedir + 'AdvSave/FGSM/model_{}/cnnEpochs_{}/epsilon_{}/'.format(args.cnn_model,
                                                                                         args.cnn_epochs, args.epsilon)

    elif args.attack_method == 2:
        alpha = 0.05
        X_train = np.clip(X_train + alpha * np.sign(np.random.randn(*X_train.shape)), 0, 1.0)
        epsilon = args.epsilon - alpha
        attack_params = {'eps': epsilon, 'clip_min': 0., 'clip_max': 1.}
        attack_obj = FastGradientMethod(model, sess=sess)
        savedir = base_savedir + 'AdvSave/RANDFGSM/model_{}/cnnEpochs_{}/epsilon_{}/'.format(args.cnn_model,
                                                                                             args.cnn_epochs,
                                                                                             args.epsilon)

    elif args.attack_method == 3:
        eps2lr_dict = {0.2: 6, 0.25: 8, 0.3: 10, 0.35: 12}
        cwlr = eps2lr_dict[args.epsilon]
        attack_obj = CarliniWagnerL2(model, back='tf', sess=sess)
        attack_params = {'binary_search_steps': 1,
                         'max_iterations': 100,
                         'learning_rate': cwlr,
                         'batch_size': batch_size,
                         'initial_const': 100,
                         }
        savedir = base_savedir + 'AdvSave/CW/model_{}/cnnEpochs_{}/epsilon_{}/'.format(args.cnn_model, args.cnn_epochs,
                                                                                       args.epsilon)
    if not os.path.exists(savedir):
        os.makedirs(savedir)
    adv_x = attack_obj.generate(x, **attack_params)
    preds_adv = model.get_probs(adv_x)
    eval_par = {'batch_size': batch_size}

    nb_batches = int(math.ceil(float(len(X_train)) / batch_size))
    assert nb_batches * batch_size >= len(X_train)
    X_cur = np.zeros((batch_size,) + X_train.shape[1:],
                     dtype=X_train.dtype)
    adv_l = []
    for batch in range(nb_batches):
        start = batch * batch_size
        end = min(len(X_train), start + batch_size)
        cur_batch_size = end - start
        X_cur[:cur_batch_size] = X_train[start:end]
        feed_dict = {x: X_cur}
        cur_adv = adv_x.eval(feed_dict=feed_dict)
        adv_l.append(cur_adv)
    adv_examples = np.vstack(adv_l)[0:60000]
    acc = model_eval(sess, x, y, preds_adv, X_train, Y_train, args=eval_par)

np.save(savedir + 'adv_x.npy', adv_examples)
np.save(savedir + 'xt.npy', X_train)
np.save(savedir + 'yt.npy', Y_train)
np.save(savedir + 'adv_acc.npy', acc)
