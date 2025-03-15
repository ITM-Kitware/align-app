# CHANGELOG


## v0.1.0 (2025-03-15)

### Bug Fixes

- **multiprocess_decider**: Free gpu memory before recreating
  ([`3b7c4d9`](https://github.com/ITM-Kitware/align-app/commit/3b7c4d91ee7f7b07a205706c3bc8532bd310cc26))

### Chores

- **test_and_release**: Target main branch and python 3.10
  ([`9f3354d`](https://github.com/ITM-Kitware/align-app/commit/9f3354d67c6f9b2035bde06eb5f0cfc417f13b60))

### Documentation

- Convert README and CONTRIBUTING to markdown
  ([`6f93b0b`](https://github.com/ITM-Kitware/align-app/commit/6f93b0b5b45a03c57a0c2b4ce71f0b65ee2077b3))

### Features

- Add alignment target parameter
  ([`3490772`](https://github.com/ITM-Kitware/align-app/commit/349077208ec299fdb3d808ad794544d907bb1715))

- Add decision maker parameter
  ([`57917ac`](https://github.com/ITM-Kitware/align-app/commit/57917ac117432c793a77b4f67255f31a05f6b2a6))

- Add select input for scenario
  ([`78e3eb1`](https://github.com/ITM-Kitware/align-app/commit/78e3eb103462d93a596f7947bd27ad76b6b965e3))

- Add waiting for decision spinner
  ([`1cb683f`](https://github.com/ITM-Kitware/align-app/commit/1cb683f2b69a4c2db4054eaff05b9198cad5f29c))

- Avoid snake case in UI
  ([`1895b84`](https://github.com/ITM-Kitware/align-app/commit/1895b849c1fc9f9495b55960d5d38afd484a337c))

Closes #15

- Init align library
  ([`cfd9371`](https://github.com/ITM-Kitware/align-app/commit/cfd93716de88fd60e97ae6462fc2bce4320f2e4b))

- Init with trame cookiecutter
  ([`2be8a94`](https://github.com/ITM-Kitware/align-app/commit/2be8a9468ba58fa5ab4d0b594c7f4430617294d8))

https://github.com/Kitware/trame-cookiecutter

- Output layout with expansion panels
  ([`ebf28e1`](https://github.com/ITM-Kitware/align-app/commit/ebf28e1ecd1255c939456f58e4b8883d02e774c6))

- Remove vtk window and setup hot reload
  ([`a5b2f86`](https://github.com/ITM-Kitware/align-app/commit/a5b2f8613014b96235215088e4c2e221541bd648))

Cleans some boilerplate and sets up trame's hot reload dev hack. Run align-app --hot-reload and a
  reload button appears for quick GUI tweaks.

- Seed prompt with default
  ([`47f3f79`](https://github.com/ITM-Kitware/align-app/commit/47f3f79355c031e6b9140fa6d63a166536f1caff))

- Support multiple alignment targets
  ([`f97e4e6`](https://github.com/ITM-Kitware/align-app/commit/f97e4e699cce873a597ea4cd272f76c4596d3235))

- **ui**: Chat layout
  ([`fc848e8`](https://github.com/ITM-Kitware/align-app/commit/fc848e8622b510c101a4c6ddae04cd480676d6d8))

- **ui**: Match alignment card position for input and output
  ([`3567137`](https://github.com/ITM-Kitware/align-app/commit/356713781447064a8f7ae620a9114cd84efe1c8f))

- **ui**: Prompt input always at bottom
  ([`9b5f95c`](https://github.com/ITM-Kitware/align-app/commit/9b5f95c50e5ed27a07af258038893a68a3d9839d))

- **ui**: Put Decision in same ExpansionPanels as Prompt
  ([`ee4a1b1`](https://github.com/ITM-Kitware/align-app/commit/ee4a1b154e9d4ebfba148c34fad1cb8beb4428d8))

### Refactoring

- Run align system in subprocess
  ([`8c2513f`](https://github.com/ITM-Kitware/align-app/commit/8c2513f9818c0eea8bb0bf76661491a1dbc4d1c5))

closes #5

- Use align_system ADM
  ([`d6227fc`](https://github.com/ITM-Kitware/align-app/commit/d6227fca4784a6d62063ab2a8239bf6bdffcd2cc))

- Use common get_id func
  ([`6bcc001`](https://github.com/ITM-Kitware/align-app/commit/6bcc001718d16fdcb5a732713c8ec7dab561e30e))

- **decider**: Retain essential prompt and decision code
  ([`991c944`](https://github.com/ITM-Kitware/align-app/commit/991c944ade2db956dbce84cf9c4f25cef796fd1e))
