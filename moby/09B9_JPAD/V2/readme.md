Level 44 NTSC

## `code.0003`

## Registry / Blob Entries

| What                                                | Address    | Size   | Category        |
|-----------------------------------------------------|------------|--------|-----------------|
| Registry slot (`class=09B9`, `primary=custom_main`) | `0x003BB430` | 12 B   | 09B9-specific   |
| 10C4 secondary blob copy                            | `0x003BBAD8` | 48 B   | 09B9-specific   |

---

## `code.0006` — overwrite

| What                           | Address    | Size | Category                  |
|--------------------------------|------------|------|---------------------------|
| Compare site → `j launch_hook` | `0x00515A20` | 8 B  | Shared hook (10C4 path)   |

---

## `code.0006` — appended

| What                | Address    | Size    | Category        |
|---------------------|------------|---------|-----------------|
| `custom_main`       | `0x0053FA70` | 2048 B  | 09B9-specific   |
| `launch_hook`       | `0x00540270` | 188 B   | Shared hook     |
| `velocity_wrapper`  | `0x0054032C` | 152 B   | 09B9-specific   |
| `visual_helper`     | `0x005403C4` | 92 B    | 09B9-specific   |
| `pending_ptr`       | `0x00540420` | 4 B     | 09B9-specific   |
| `pulse_table`       | `0x00540444` | 64 B    | 09B9-specific   |
| `pulse_color_table` | `0x00540484` | 64 B    | 09B9-specific   |
| `default_params`    | `0x005404C4` | 8 B     | 09B9-specific   |
