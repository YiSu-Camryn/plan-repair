private boolean isJavaProperty(final String token) {
    // Assuming that the '=' character is used to delimit the key and value in the token
    int delimiterIndex = token.indexOf('='); 
    final String opt = delimiterIndex != -1 ? token.substring(0, delimiterIndex) : token;
    final Option option = options.getOption(opt);

    return option != null && (option.getArgs() >= 2 || option.getArgs() == Option.UNLIMITED_VALUES);
}