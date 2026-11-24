//! Pure close coordination. A missing response is never consent to exit.
use std::collections::BTreeSet;

#[derive(Clone, Debug, PartialEq)]
pub enum Scope {
    App,
    Window(String),
}

#[derive(Clone, Debug)]
pub struct Request {
    pub id: u64,
    pub scope: Scope,
    pub members: BTreeSet<String>,
    waiting: BTreeSet<String>,
}

#[derive(Default)]
pub struct Coordinator {
    next: u64,
    pending: Option<Request>,
    exporting: bool,
}

impl Coordinator {
    pub fn active(&self) -> bool {
        self.pending.is_some() || self.exporting
    }

    pub fn begin_export(&mut self) -> bool {
        if self.active() {
            return false;
        }
        self.exporting = true;
        true
    }

    pub fn finish_export(&mut self) {
        self.exporting = false;
    }

    pub fn begin(&mut self, scope: Scope, members: BTreeSet<String>) -> Option<Request> {
        if self.active() {
            return None;
        }
        self.next += 1;
        let request = Request {
            id: self.next,
            scope,
            waiting: members.clone(),
            members,
        };
        self.pending = Some(request.clone());
        Some(request)
    }

    pub fn accepts(&self, id: u64, window: &str) -> bool {
        self.pending
            .as_ref()
            .is_some_and(|r| r.id == id && r.waiting.contains(window))
    }

    pub fn acknowledge(&mut self, id: u64, window: &str) -> Result<bool, &'static str> {
        if !self.accepts(id, window) {
            return Err("No pending close response for this window");
        }
        let request = self.pending.as_mut().unwrap();
        request.waiting.remove(window);
        Ok(request.waiting.is_empty())
    }

    pub fn cancel(&mut self, id: u64) -> Option<Request> {
        if self.pending.as_ref().is_some_and(|r| r.id == id) {
            self.pending.take()
        } else {
            None
        }
    }

    pub fn timeout(&mut self, id: u64) -> Option<Request> {
        if self
            .pending
            .as_ref()
            .is_some_and(|r| r.id == id && !r.waiting.is_empty())
        {
            self.pending.take()
        } else {
            None
        }
    }

    pub fn finish(&mut self, id: u64) -> Option<Scope> {
        if self
            .pending
            .as_ref()
            .is_some_and(|r| r.id == id && r.waiting.is_empty())
        {
            self.pending.take().map(|r| r.scope)
        } else {
            None
        }
    }

    pub fn current(&self) -> Option<Request> {
        self.pending.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn members() -> BTreeSet<String> {
        ["main", "evidence-0"].map(String::from).into()
    }

    #[test]
    fn all_windows_must_reply_before_confirmation() {
        let mut c = Coordinator::default();
        let r = c.begin(Scope::App, members()).unwrap();
        assert_eq!(c.finish(r.id), None);
        assert_eq!(c.acknowledge(r.id, "main"), Ok(false));
        assert_eq!(c.finish(r.id), None);
        assert_eq!(c.acknowledge(r.id, "evidence-0"), Ok(true));
        assert!(c.timeout(r.id).is_none()); // User confirmation has no auto-exit timeout.
        assert_eq!(c.finish(r.id), Some(Scope::App));
        assert!(!c.active());
    }

    #[test]
    fn duplicate_unknown_and_stale_responses_cannot_close() {
        let mut c = Coordinator::default();
        let a = c.begin(Scope::App, members()).unwrap();
        assert!(c.begin(Scope::App, members()).is_none());
        assert!(c.acknowledge(a.id, "foreign").is_err());
        c.acknowledge(a.id, "main").unwrap();
        assert!(c.acknowledge(a.id, "main").is_err());
        assert!(c.cancel(a.id).is_some());
        let b = c.begin(Scope::App, members()).unwrap();
        assert_ne!(a.id, b.id);
        assert!(c.acknowledge(a.id, "evidence-0").is_err());
        assert!(c.cancel(a.id).is_none());
        assert!(c.timeout(a.id).is_none());
        assert!(c.finish(a.id).is_none());
        assert!(c.active());
    }

    #[test]
    fn timeout_never_approves_exit() {
        let mut c = Coordinator::default();
        let r = c.begin(Scope::App, members()).unwrap();
        assert!(c.timeout(r.id).is_some());
        assert!(c.finish(r.id).is_none());
        assert!(c.acknowledge(r.id, "main").is_err());
    }

    #[test]
    fn evidence_close_has_only_one_member_and_keeps_app_scope_separate() {
        let mut c = Coordinator::default();
        let scope = Scope::Window("evidence-0".into());
        let r = c
            .begin(scope.clone(), ["evidence-0".into()].into())
            .unwrap();
        assert!(c.acknowledge(r.id, "main").is_err());
        assert_eq!(c.acknowledge(r.id, "evidence-0"), Ok(true));
        assert_eq!(c.finish(r.id), Some(scope));
    }

    #[test]
    fn untouched_launcher_can_confirm_without_a_frontend() {
        let mut c = Coordinator::default();
        let r = c.begin(Scope::App, BTreeSet::new()).unwrap();
        assert!(c.timeout(r.id).is_none());
        assert_eq!(c.finish(r.id), Some(Scope::App));
    }

    #[test]
    fn export_and_close_are_mutually_exclusive() {
        let mut c = Coordinator::default();
        assert!(c.begin_export());
        assert!(!c.begin_export());
        assert!(c.begin(Scope::App, members()).is_none());
        assert!(c
            .begin(Scope::Window("evidence-0".into()), members())
            .is_none());
        c.finish_export();
        let request = c.begin(Scope::App, members()).unwrap();
        assert!(!c.begin_export());
        c.cancel(request.id);
        assert!(c.begin_export());
    }
}
