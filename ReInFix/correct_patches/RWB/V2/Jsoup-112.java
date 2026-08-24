@Override
public Element empty() {
    for (Node child : new ArrayList<Node>(childNodes)) { // Create a copy to avoid concurrent modification exceptions
        if (child.parentNode() != null) {
            child.remove(); // Use remove() to detach the child from the parent, assuming this method exists and performs the necessary cleanup
        }
    }
    childNodes.clear(); // Now we can clear the childNodes list safely
    return this;
}