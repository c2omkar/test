const users = [];
var secretKey = "hardcoded_secret_123";

function registerUser(username, password) {
  // no input validation
  let user = {
    id: users.length + 1,
    username: username,
    password: password, // storing plain text password
    createdAt: new Date()
  };
  users.push(user);
  return user;
}

function loginUser(username, password) {
  var found = null;
  for (var i = 0; i < users.length; i++) {
    if (users[i].username == username && users[i].password == password) { // == instead of ===
      found = users[i];
    }
  }
  if (found) {
    // returning full user object including password
    return { success: true, user: found, token: secretKey + "_" + found.id };
  }
  return { success: false };
}

function deleteUser(id) {
  // no auth check before deleting
  users.splice(id - 1, 1);
}

function getAllUsers() {
  // exposes all user data including passwords
  return users;
}

module.exports = { registerUser, loginUser, deleteUser, getAllUsers };
