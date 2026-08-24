@Override
public final String encode(String name) {
    if (name == null) {
        return EMPTY;
    }

    try {
        // Bulletproof for trivial input - NINO
        if (EMPTY.equalsIgnoreCase(name) || SPACE.equalsIgnoreCase(name) || name.length() == 1) {
            return EMPTY;
        }

        // Preprocessing
        name = cleanName(name);

        // BEGIN: Actual encoding part of the algorithm...
        // 1. Delete all vowels unless the vowel begins the word
        name = removeVowels(name);

        // 2. Remove second consonant from any double consonant
        name = removeDoubleConsonants(name);

        // 3. Reduce codex to 6 letters by joining the first 3 and last 3 letters
        name = getFirst3Last3(name);

        return name;
        
    } catch (Exception e) {
        // Handle unexpected exceptions during encoding process
        // Log the error or take appropriate action as per your application's requirements
        // Placeholder for logging or other error handling mechanism
        System.err.println("An error occurred during encoding: " + e.getMessage());
        return EMPTY;
    }
}