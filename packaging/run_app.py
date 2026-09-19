# Frozen-app entry point. Keep the multiprocessing guard FIRST — before the
# PyQt import chain — so that worker processes spawned by the library scan
# (ParallelTagReader) short-circuit here instead of paying the full GUI import
# cost on every worker. freeze_support() is a no-op when not frozen.
import multiprocessing

multiprocessing.freeze_support()

from cratesort.src.gui.main_window import main

if __name__ == '__main__':
    main()
