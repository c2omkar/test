class AppError extends Error {
  constructor(message, statusCode = 500) {
    super(message);
    this.statusCode = statusCode;
    this.name = "AppError";
  }
}

function handleError(err) {
  console.error(`[${err.name || "Error"}] ${err.message}`);
  return { success: false, message: err.message, statusCode: err.statusCode || 500 };
}

module.exports = { AppError, handleError };
