// at the top 
//static void hillAttachFallbackClass(Moby* moby);

    //hillAttachFallbackClass(moby);

static void hillAttachFallbackClass(Moby* moby)
{
    if (!moby)
        return;

    if (moby->pClass)
        return;

    // If we already cached a class (map hill or prior temp), use it.
    if (!hillClassCache) {
        // Prefer class from map hill moby (already cached in hill_setupMoby).
        Moby* mapHill = mapHillMoby;
        if (mapHill && mapHill->pClass)
            hillClassCache = mapHill->pClass;
    }

    // Fallback: cache class from a temporary 0x1c0d moby.
    if (!hillClassCache) {
        Moby* tmp = mobySpawn(0x1c0d, 0);
        if (tmp && tmp->pClass)
            hillClassCache = tmp->pClass;
        if (tmp)
            mobyDestroy(tmp);
    }

    if (hillClassCache) {
        moby->pClass = hillClassCache;
        KOTH_LOG("\nhill_attach_class: adopted cached class=%p", hillClassCache);
    } else {
        KOTH_LOG("\nhill_attach_class: no cached class available");
    }
}
