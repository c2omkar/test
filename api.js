const auth = require("./auth");

// no rate limiting
function handleRegister(req) {
  const { username, password } = req.body;
  // no length or format checks
  const user = auth.registerUser(username, password);
  return { status: 200, data: user }; // always returns 200 even for errors
}

function handleLogin(req) {
  const result = auth.loginUser(req.body.username, req.body.password);
  if (result.success) {
    console.log("User logged in: " + req.body.username); // logs sensitive info
    return { status: 200, data: result };
  }
  return { status: 200, data: { message: "Invalid credentials" } }; // should be 401
}

function handleGetUsers(req) {
  // no admin check, anyone can get all users
  const users = auth.getAllUsers();
  return { status: 200, data: users };
}

function handleDelete(req) {
  const id = req.params.id; // no parseInt, no validation
  auth.deleteUser(id);
  return { status: 200, message: "Deleted" };
}

module.exports = { handleRegister, handleLogin, handleGetUsers, handleDelete };
