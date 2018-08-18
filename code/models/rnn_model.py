import pdb
import os
import keras
import tqdm
from models.base_model import BaseModel
from utils import utils
from keras.models import Sequential, Model, load_model
from keras.layers import Dense, Dropout, Embedding, LSTM, Bidirectional, Input, Lambda
from keras import backend as K
from utils.text_utils import WordVectorizer
from utils import utils
from keras.callbacks import EarlyStopping
from keras.utils import multi_gpu_model
from keras.preprocessing.sequence import pad_sequences
from nltk.tokenize.toktok import ToktokTokenizer


class RNNModel(BaseModel):
    def __init__(self, num_classes, index2word, embedding_size=200, hidden_size=256):
        super(RNNModel, self).__init__()
        self.hidden_size = 256
        self.num_classes = num_classes
        self.vocab_size = len(index2word)
        self.embedding_size = embedding_size
        self.lang = WordVectorizer(index2word)
        self.encoder = self.get_encoder()
        self.encoder.summary()

        self.language_model = self.get_lm_decoder(self.encoder, self.vocab_size)
        self.language_model.summary()

        self.classifier = self.get_classifier_decoder(self.encoder, num_classes)
        self.classifier.summary()

    def save(self, directory):
        self.language_model.save_weights(os.path.join(directory, 'language_model.h5'))
        self.classifier.save_weights(os.path.join(directory, 'classifier.h5'))

    def load(self, directory):
        self.language_model.load_weights(os.path.join(directory, 'language_model.h5'))
        self.classifier.load_weights(os.path.join(directory, 'classifier.h5'))

    def get_encoder(self):
        vec_input = Input(shape=(None,))
        x = Embedding(self.vocab_size, self.embedding_size)(vec_input)
        x = LSTM(self.hidden_size, return_sequences=True)(x)
        x = LSTM(self.hidden_size, return_sequences=True)(x)
        x = LSTM(self.hidden_size, return_sequences=True)(x)
        model = Model(vec_input, x)
        model.compile('adam', 'categorical_crossentropy', metrics=['accuracy'])
        return model

    def get_classifier_decoder(self, encoder, num_classes):
        vec_input = Input(shape=(None,))
        x = encoder(vec_input)
        x = Lambda(lambda x: x[:, -1, :], output_shape=(self.hidden_size,))(x)
        decode = Dense(num_classes, activation='softmax')(x)
        model = Model(vec_input, decode)
        model.compile('adam', 'categorical_crossentropy', metrics=['accuracy'])
        return model

    def get_lm_decoder(self, encoder, num_classes):
        # batch x seq_len x 128
        vec_input = Input(shape=(None,))
        x = encoder(vec_input)
        decode = Dense(num_classes, activation='softmax')(x)
        model = Model(vec_input, decode)
        model.compile('adam', 'categorical_crossentropy', metrics=['accuracy'])
        return model

    def _create_bptt_data(self, x_texts, bptt):
        tokenizer = ToktokTokenizer()
        all_text = ' \n '.join(x_texts)
        tokenized = tokenizer.tokenize(all_text)
        chunks = [tokenized[i:i + bptt + 1] for i in range(0, len(tokenized), bptt + 1)]
        return chunks

    def representation_learning(
        self,
        x_texts,
        epochs=1,
        bptt=100,
        batch_size=32,
        verbose=False,
        num_gpus=1,
    ):
        all_chunks = self._create_bptt_data(x_texts, bptt)

        batches = [all_chunks[i:i + batch_size] for i in range(0, len(all_chunks), batch_size)]
        total_losses = []
        if num_gpus > 1:
            batch_size = batch_size * num_gpus
            model = multi_gpu_model(self.language_model, gpus=num_gpus)
            model.compile('adam', 'categorical_crossentropy', metrics=['accuracy'])
            print("Set batch size to {}".format(batch_size))
        else:
            model = self.language_model

        with self.graph.as_default():
            for epoch in range(epochs):
                iterable = tqdm.tqdm(batches) if verbose else batches
                total_loss = 0.
                for tokens_batch in iterable:
                    # Compute x_batch and y_batch
                    x_text = pad_sequences(self.lang._sequence_ids(tokens_batch))
                    x_train = x_text[:, :-1]
                    y_train = x_text[:, 1:]
                    target = utils.one_hot_encode(y_train, self.vocab_size)

                    # Train language model.
                    result = model.fit(x_train, target, batch_size=batch_size, verbose=0)
                    total_loss += 1 / len(iterable) * result.history['loss'][-1]

                if verbose: print("Epoch: {} | Loss: {}".format(epoch, total_loss))

                total_losses.append(total_loss / len(tokens_batch))
        return (total_losses, 0.)

    def vectorize_text(self, x_texts):
        x_train, lengths = self.lang.texts_to_sequence(x_texts)
        return x_train

    def fit(self, x_texts, y_train, validation_split=0, epochs=1):
        y_train = utils.one_hot_encode(y_train, self.num_classes)
        x_train = self.vectorize_text(x_texts)
        if validation_split > 0.:
            callbacks = [EarlyStopping(patience=3)]
        else:
            callbacks = None

        with self.graph.as_default():
            history = self.classifier.fit(
                x_train,
                y_train,
                validation_split=validation_split,
                callbacks=callbacks,
                epochs=epochs,
                verbose=0,
            )
            return history.history

    def evaluate(self, x_texts, y_test):
        y_test = utils.one_hot_encode(y_test, self.num_classes)
        x_test = self.vectorize_text(x_texts)
        with self.graph.as_default():
            return self.classifier.evaluate(x_test, y_test)

    def score(self, x_texts):
        x_scores = self.vectorize_text(x_texts)
        with self.graph.as_default():
            return self.classifier.predict(x_scores)

    def predict(self, x):
        x_scores = self.vectorize_text(x_texts)
        with self.graph.as_default():
            return self.classifier.predict(x_scores)
