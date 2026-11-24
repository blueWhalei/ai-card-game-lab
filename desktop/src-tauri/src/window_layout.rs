//! Preserve Windows workspace coordinates; never mix these with screen coordinates.
use serde::{Deserialize, Serialize};
use windows_sys::Win32::{
    Foundation::{POINT, RECT},
    UI::WindowsAndMessaging::{
        GetWindowPlacement, SetWindowPlacement, SW_SHOWMAXIMIZED, SW_SHOWMINIMIZED, SW_SHOWNORMAL,
        WINDOWPLACEMENT, WPF_RESTORETOMAXIMIZED,
    },
};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Layout {
    left: i32,
    top: i32,
    right: i32,
    bottom: i32,
    maximized: bool,
}

impl Layout {
    pub fn validate(&self) -> Result<(), String> {
        let width = i64::from(self.right) - i64::from(self.left);
        let height = i64::from(self.bottom) - i64::from(self.top);
        if !(100..=65536).contains(&width)
            || !(100..=65536).contains(&height)
            || [self.left, self.top, self.right, self.bottom]
                .iter()
                .any(|coordinate| i64::from(*coordinate).abs() > 1_000_000)
        {
            return Err("Invalid main window layout".into());
        }
        Ok(())
    }

    fn from_placement(value: &WINDOWPLACEMENT) -> Result<Self, String> {
        let rect = value.rcNormalPosition;
        let layout = Self {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            maximized: value.showCmd == SW_SHOWMAXIMIZED as u32
                || (value.showCmd == SW_SHOWMINIMIZED as u32
                    && value.flags & WPF_RESTORETOMAXIMIZED != 0),
        };
        layout.validate()?;
        Ok(layout)
    }

    fn placement(&self) -> WINDOWPLACEMENT {
        WINDOWPLACEMENT {
            length: std::mem::size_of::<WINDOWPLACEMENT>() as u32,
            showCmd: if self.maximized {
                SW_SHOWMAXIMIZED
            } else {
                SW_SHOWNORMAL
            } as u32,
            ptMaxPosition: POINT { x: -1, y: -1 },
            ptMinPosition: POINT { x: -1, y: -1 },
            rcNormalPosition: RECT {
                left: self.left,
                top: self.top,
                right: self.right,
                bottom: self.bottom,
            },
            ..Default::default()
        }
    }

    pub fn capture(window: &tauri::WebviewWindow) -> Result<Self, String> {
        let handle = window.hwnd().map_err(|e| e.to_string())?;
        let mut placement = WINDOWPLACEMENT {
            length: std::mem::size_of::<WINDOWPLACEMENT>() as u32,
            ..Default::default()
        };
        // The live main-window handle and initialized output structure belong to this call.
        if unsafe { GetWindowPlacement(handle.0, &mut placement) } == 0 {
            return Err("Unable to read main window layout".into());
        }
        Self::from_placement(&placement)
    }

    pub fn restore(&self, window: &tauri::WebviewWindow) -> Result<(), String> {
        self.validate()?;
        let handle = window.hwnd().map_err(|e| e.to_string())?;
        // Windows adjusts a completely off-screen placement to the current display layout.
        if unsafe { SetWindowPlacement(handle.0, &self.placement()) } == 0 {
            return Err("Unable to restore main window layout".into());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    pub fn sample() -> Layout {
        Layout {
            left: -1300,
            top: 40,
            right: -100,
            bottom: 840,
            maximized: false,
        }
    }

    #[test]
    fn preserves_normal_bounds_and_maximized_state_without_reopening_minimized() {
        let mut layout = sample();
        assert_eq!(Layout::from_placement(&layout.placement()).unwrap(), layout);
        layout.maximized = true;
        assert_eq!(Layout::from_placement(&layout.placement()).unwrap(), layout);
        let mut minimized = layout.placement();
        minimized.showCmd = SW_SHOWMINIMIZED as u32;
        minimized.flags = WPF_RESTORETOMAXIMIZED;
        assert_eq!(Layout::from_placement(&minimized).unwrap(), layout);
        minimized.flags = 0;
        assert_eq!(
            Layout::from_placement(&minimized)
                .unwrap()
                .placement()
                .showCmd,
            SW_SHOWNORMAL as u32
        );
    }

    #[test]
    fn rejects_invalid_bounds_without_integer_overflow() {
        for (left, right) in [(0, 0), (1000, 0), (0, 70000), (i32::MIN, i32::MAX)] {
            let mut layout = sample();
            layout.left = left;
            layout.right = right;
            assert!(layout.validate().is_err());
        }
        let mut layout = sample();
        layout.bottom = layout.top;
        assert!(layout.validate().is_err());
        assert!(sample().validate().is_ok());
    }
}
