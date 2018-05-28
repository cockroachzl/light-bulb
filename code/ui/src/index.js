import React from 'react';
import ReactDOM from 'react-dom';

import thunk from 'redux-thunk';
import { createStore, applyMiddleware, compose, combineReducers } from 'redux';
import { Provider } from 'react-redux';

import createHistory from 'history/createBrowserHistory';
import { Route } from 'react-router';

import { ConnectedRouter, routerReducer, routerMiddleware } from 'react-router-redux';

import LabelAppContainer from './containers/LabelApp';
import DemoAppContainer from './containers/DemoApp';
import { getTask, getNextBatch, getStats } from './actions';
import reducer from './reducers';

const history = createHistory();
const middleware = [
  thunk,
  routerMiddleware(history),
];

const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;
const store = createStore(
  combineReducers({
    ...reducer,
    router: routerReducer,
  }),
  composeEnhancers(applyMiddleware(...middleware)),
);
const rootEl = document.getElementById('root');
// eslint-disable-next-line react/no-render-return-value
const render = () => ReactDOM.render(
  // eslint-disable-next-line react/jsx-filename-extension
  <Provider store={store}>
    <ConnectedRouter history={history}>
      <div>
        <Route exact path="/" component={LabelAppContainer} />
        <Route exact path="/demo" component={DemoAppContainer} />
      </div>
    </ConnectedRouter>
  </Provider>,
  rootEl,
);

render();
store.subscribe(render);
store.dispatch(getTask());
store.dispatch(getNextBatch());
store.dispatch(getStats());