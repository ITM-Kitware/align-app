# CHANGELOG


## v0.7.1 (2025-04-24)

### Bug Fixes

- **ui**: Change correct column on run number selection
  ([`26cc9cc`](https://github.com/ITM-Kitware/align-app/commit/26cc9cc51b32ad2c16d86bc2490044096f8d36ca))

### Refactoring

- **adm_core**: More readable get_dataset_decider_configs
  ([`6e05d3a`](https://github.com/ITM-Kitware/align-app/commit/6e05d3acdc63dbb9dedd0b2a476e47d8142506ca))


## v0.7.0 (2025-04-15)

### Bug Fixes

- Kaleido gets continuous value kdma
  ([`daea766`](https://github.com/ITM-Kitware/align-app/commit/daea766a897e756e0d0baa34b33dd7bd966dd776))

### Documentation

- **readme**: Add interaction flow and benefits
  ([`c3d07ab`](https://github.com/ITM-Kitware/align-app/commit/c3d07abf249556374d949adf8ef755435c77c5da))

### Features

- Show alignment attribute description
  ([`05463d8`](https://github.com/ITM-Kitware/align-app/commit/05463d893e1fb14dd22efac29bacb3d14aae7712))

- **prompt**: Show alignment target descriptions in prompt
  ([`74aff16`](https://github.com/ITM-Kitware/align-app/commit/74aff16ee325771621e9141ca6f289838a283815))

### Refactoring

- **prompt**: Put attribute id arg first
  ([`2130bd9`](https://github.com/ITM-Kitware/align-app/commit/2130bd93a5379fbb553f17c7c86d4acd7949b6d7))


## v0.6.1 (2025-04-10)

### Bug Fixes

- **pyproject**: Point to align-system branch with kaleido changes
  ([`b4c6460`](https://github.com/ITM-Kitware/align-app/commit/b4c646048ed7c11cb6c7b2a21bcdb3b25be9a8f1))


## v0.6.0 (2025-04-09)

### Bug Fixes

- **adm_core**: Remove baseline from kaleido config
  ([`51dcfad`](https://github.com/ITM-Kitware/align-app/commit/51dcfad30c61bf4f1b9ab8fc6d3562b1302a03fe))

- **adm_core**: Try to cleanup kaleido
  ([`8e20070`](https://github.com/ITM-Kitware/align-app/commit/8e20070b5822663a8d62a28df41ad1318d6b69a3))

### Features

- Add run picking select in columns
  ([`dd41c84`](https://github.com/ITM-Kitware/align-app/commit/dd41c84db84564dd9e9f4e8eb526a7dc537b5409))


## v0.5.0 (2025-04-08)

### Bug Fixes

- **adm_core**: Limit kaleido alignment attributes to 1
  ([`79fda7d`](https://github.com/ITM-Kitware/align-app/commit/79fda7d077f42d21c7eba4e313985bc9c5738e3a))

### Chores

- **README**: Fix dev poetry install command
  ([`941d498`](https://github.com/ITM-Kitware/align-app/commit/941d498d029e3f4f587652ce5d56be21673d4602))

### Features

- **adm_core**: Make system prompt for kaleido
  ([`d0d711b`](https://github.com/ITM-Kitware/align-app/commit/d0d711bd722095e94dd898bd6b5bcce5cbe8fcac))

### Refactoring

- **adm_core**: Pull decider configs from datasets
  ([`ad2998e`](https://github.com/ITM-Kitware/align-app/commit/ad2998e663f8c46a2b77e326ed6f107fa2e138ba))


## v0.4.2 (2025-04-04)

### Bug Fixes

- Point to working align-system
  ([`2d54041`](https://github.com/ITM-Kitware/align-app/commit/2d54041278cc63ad4e890b038f90725ffe49abcf))

Switch to using poetry


## v0.4.1 (2025-04-02)

### Bug Fixes

- **adm_core**: Remove options from opinionqa scenario
  ([`8bb2c77`](https://github.com/ITM-Kitware/align-app/commit/8bb2c77f648551f9d7c9e84ee325da7d02255d66))

### Chores

- **pyproject**: Set align-system to tag 0.5.7
  ([`5ef202a`](https://github.com/ITM-Kitware/align-app/commit/5ef202a308070d7b4120945c82f785015de4411f))


## v0.4.0 (2025-04-02)

### Bug Fixes

- **adm_core**: Call kaleido correctly
  ([`bbabffd`](https://github.com/ITM-Kitware/align-app/commit/bbabffd3e12db6ab92f4755baf63c740911f7b24))

### Features

- **prompt**: Validate prompt when kaleido selected
  ([`bab1e15`](https://github.com/ITM-Kitware/align-app/commit/bab1e154e78dc5584e8c3081d6bf117cdaf3f952))


## v0.3.0 (2025-03-28)

### Features

- Add NAACL24 dataset
  ([`24028a4`](https://github.com/ITM-Kitware/align-app/commit/24028a4492ce3f8928d47440beead84cdb8d343c))

- Add numbers to choices
  ([`b2a1e80`](https://github.com/ITM-Kitware/align-app/commit/b2a1e800252bb989e54216b6141e2c5e77cb624a))

- Add opinionQA dataset
  ([`e3ef69e`](https://github.com/ITM-Kitware/align-app/commit/e3ef69e775a39b1d81612a496730e0ffadbf9609))

- Add system prompt
  ([`0adbf75`](https://github.com/ITM-Kitware/align-app/commit/0adbf754fecc7f474e5286787cd07f57c4ef199d))

- Label choices with letter not number
  ([`1a4b5df`](https://github.com/ITM-Kitware/align-app/commit/1a4b5df0c34cdc26c13153ae01b2a1c2a416c647))

- No score slider for opinionqa attributes
  ([`a865af9`](https://github.com/ITM-Kitware/align-app/commit/a865af94d50813522b247085bcd11c4215757c8c))

- Stub kaleido
  ([`c6832fc`](https://github.com/ITM-Kitware/align-app/commit/c6832fcdffbb5d1a5d507141755756b0c76cdd6c))

- **ui**: Add Run row
  ([`1ba26a2`](https://github.com/ITM-Kitware/align-app/commit/1ba26a2c918ba7453cf19f6e06843269d87eb708))


## v0.2.0 (2025-03-21)

### Bug Fixes

- **adm_core**: Filter choices
  ([`dc8fd76`](https://github.com/ITM-Kitware/align-app/commit/dc8fd7648f108c3b183c7ff9c39878ad10d25c31))

- **adm_core**: Set backbone on instance
  ([`94953ec`](https://github.com/ITM-Kitware/align-app/commit/94953ecce79966a89ba0b6b8a5f3f4034644ecba))

- **ui**: Keep panel title from overflowing
  ([`424b56c`](https://github.com/ITM-Kitware/align-app/commit/424b56ccb8d57d1a3e7e0b4a6d97d3a472f9c47e))

### Features

- Add characters to scenario ui
  ([`66625ed`](https://github.com/ITM-Kitware/align-app/commit/66625ed5e80c1bb7cb1e94d690314618f6a04447))

- **ui**: Better typography and decision maker order
  ([`026bc59`](https://github.com/ITM-Kitware/align-app/commit/026bc59f6faf52f3de2466fc716cc000fe992944))

- **ui**: Put prompt input in right column
  ([`f64b4c0`](https://github.com/ITM-Kitware/align-app/commit/f64b4c0db2eec6f00d7f14c7dfcb619ab484236a))

- **ui**: Side by side comparsion layout
  ([`e9e6d66`](https://github.com/ITM-Kitware/align-app/commit/e9e6d66b29a82e1ef034bde1210b75f00c87f201))

### Refactoring

- **ui**: Break rows into classes
  ([`11860b0`](https://github.com/ITM-Kitware/align-app/commit/11860b00b607692808fc8505b66b7bed80eae956))


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
