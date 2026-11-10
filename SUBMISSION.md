# Submission

Fork URL: <!-- paste the URL of your fork here -->

## Files to commit

- [ ] `handler.py`: the function (the S3 plumbing and the validation)
- [ ] `notes.md` with your commands and what you saw (optional)

## Questions

Answer in your own words. Where a question asks for output, paste it in a code block.

### Q1. Paste the S3 notification configuration of the bucket. Why do both a prefix (`inbox/`) and a suffix (`.csv`) matter? What would happen if the Lambda wrote its report to the same prefix that triggers it, without the filter?

**Your answer:**

<!-- replace this line with your answer -->

### Q2. Paste your role policy. Which actions on which resources did you allow, and which did you refuse the function to be able to do? What would a leaked function (or a bug) be able to do with `s3:*` on `*`?

**Your answer:**

<!-- replace this line with your answer -->

### Q3. S3 invokes your function, not the other way round. Which resource-based permission lets S3 call it, and what does `SourceAccount` protect against?

**Your answer:**

<!-- replace this line with your answer -->

### Q4. Upload a file named `my file+1.csv`. What key does the event contain and what does your code do about it? Show the line and say what breaks if you forget it.

**Your answer:**

<!-- replace this line with your answer -->

### Q5. Paste the log lines of one invocation. How would you know from the logs how many times the function ran for three uploads? Where would an upload that crashes the function show up, and what does S3 do about the failure?

**Your answer:**

<!-- replace this line with your answer -->

### Q6. Delivery is at-least-once. What happens if S3 delivers the same event twice to your function? Is your function safe against that, and why?

**Your answer:**

<!-- replace this line with your answer -->

### Q7. Paste the output of `./verify.sh`. It must end with **ALL CHECKS PASSED**.

**Your answer:**

<!-- replace this line with your answer -->

### Q8. **Tear down.** Paste the output of `./verify-teardown.sh`. It must end with **TEARDOWN VERIFIED**.

**Your answer:**

<!-- replace this line with your answer -->
