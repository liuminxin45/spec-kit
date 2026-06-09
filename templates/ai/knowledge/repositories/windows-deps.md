# WindowsDeps

## Role

`WindowsDeps` is a Windows shared UI/helper library used by desktop products. It
contains Qt widgets, QSE/QSS styling, MFC/GDI+ controls, setup helpers, crash
logging, shared memory, and Windows utilities.

## Load When

- Affected repositories include `WindowsDeps`.
- Task needs Qt widget behavior, QSE styles, native UI controls, setup tools,
  Windows helpers, or Qt-to-frontend parity evidence.

## Key Paths

- `qt/`: Qt custom widgets, resources, styles, translations.
- `qt/style/` and `qt/qse/`: style and QSE files.
- `NativeWinUI/`: native Windows UI controls.
- `common/`: crash log, shared memory, network/system helpers.
- `setup/` and `SetupTools/`: installer source and packaged tools.
- `userFolderMgt/`: user data folder management.

## Validation

- Use source behavior inspection for UI parity.
- Build/test route depends on the consuming product because WindowsDeps is usually
  integrated by upper projects.

## Boundaries

- Treat WindowsDeps as source behavior evidence for Qt parity, not as ownership for
  ProductSuite frontend plugin runtime fixes.

## Verify Before Use

Confirm whether the consuming product compiles WindowsDeps via solution, CMake, or
direct source inclusion.
