private void checkRequiredArgs() throws ParseException {
    if (currentOption != null && currentOption.requiresArg() && currentOption.getValues() == null) {
        throw new MissingArgumentException(currentOption);
    }
}