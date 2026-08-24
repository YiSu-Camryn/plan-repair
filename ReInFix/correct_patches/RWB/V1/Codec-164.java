@Override
public final String encode(String name) {
    // Bulletproof for trivial input - NINO
    if (name == null || EMPTY.equalsIgnoreCase(name) || SPACE.equalsIgnoreCase(name) || name.length() == 1) {
        return EMPTY;
    }

    // Preprocessing
    name = cleanName(name);

    // BEGIN: Actual encoding part of the algorithm...
    // 1. Delete all vowels unless the vowel begins the word
    try {
        name = removeVowels(name);
    } catch(Exception e) {
        System.out.println("Error in removeVowels: " + e);
        return EMPTY;
    }

    // 2. Remove second consonant from any double consonant
    try {
        name = removeDoubleConsonants(name);
    } catch(Exception e) {
        System.out.println("Error in removeDoubleConsonants: " + e);
        return EMPTY;
    }

    // 3. Reduce codex to 6 letters by joining the first 3 and last 3 letters
    try {
        name = getFirst3Last3(name);
    } catch(Exception e) {
        System.out.println("Error in getFirst3Last3: " + e);
        return EMPTY;
    }

    return name;
}