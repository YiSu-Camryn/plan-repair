@Override
public Element empty() {
    for(Node childNode : new ArrayList<>(childNodes)){
        childNode.remove();
    }
    return this;
}