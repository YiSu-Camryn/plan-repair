private boolean isJavaProperty(final String token) {
    if (token.isEmpty()) {
        return false;
    }
    final char opt = token.charAt(0);
    final Option option = options.getOption(String.valueOf(opt));

    return option != null && (option.getArgs() >= 2 || option.getArgs() == Option.UNLIMITED_VALUES);
}