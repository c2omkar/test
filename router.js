const routes = {};

function register(method, path, handler) {
  const key = `${method.toUpperCase()}:${path}`;
  routes[key] = handler;
}

function resolve(method, path) {
  const key = `${method.toUpperCase()}:${path}`;
  return routes[key] || null;
}

module.exports = { register, resolve };
