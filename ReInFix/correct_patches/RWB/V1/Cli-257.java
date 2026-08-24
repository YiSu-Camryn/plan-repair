private void checkRequiredArgs() throws ParseException {
        if (currentOption != null && currentOption.requiresArg()) {
            Object value = currentOption.getValue();
            if (value == null || "".equals(value.toString())) {   
                throw new MissingArgumentException(currentOption);
            }
        }
    }