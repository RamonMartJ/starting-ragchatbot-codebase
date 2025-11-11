Merge git worktree into the main branch

Use the git merge command to merge in all of the worktrees in the `.trees/` folder and fix any conflicts if there are any.

Once all changes have been correctly merged, remove the worktree from `.trees/` using `git worktree remove {worktree_name}` and the corresponding branch using `git branch -D {worktree_name}`.