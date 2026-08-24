private boolean isJavaProperty(final String token) {
    if (token.isEmpty()) {
        return false; // Handle the case where token is empty to avoid StringIndexOutOfBoundsException
    }
    final String opt = token.substring(0, 1);
    final Option option = options.getOption(opt);

    // Ensuring that the option is not null and meets the expected conditions
    return option != null && (option.getArgs() >= 2 || option.getArgs() == Option.UNLIMITED_VALUES);
}