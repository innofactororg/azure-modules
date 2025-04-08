## Introduction

**Innofactor Verified Solutions** (IVS) is a self-hosted registry designed to extend the principles of **Azure Verified Modules (AVM)** to patterns, resources, and utilities customized for our specific customer deliveries. IVS follows the same rigorous engineering and publishing standards as AVM, ensuring high-quality, consistent, and maintainable infrastructure-as-code solutions.

While Microsoft’s **Azure Verified Modules** should always be the first choice, there are instances where they do not fully meet our requirements. This could be due to design decisions, missing implementation features, or unresolved bugs. In such cases, **Innofactor Verified Solutions** provides trusted, well-engineered alternatives.

Patterns and deployment strategies implemented for our customers will be published in this registry, ensuring best practices are codified and readily available.

## Value Proposition

<table style="border: none; border-collapse: collapse; margin:0; padding:0;">
  <tr>
    <td style="border: none; padding:0; margin:0; width:65%">

Innofactor Verified Solutions extends the AVM initiative by introducing **custom, validated modules** tailored for our unique delivery needs.

- **Aligned with AVM standards** – Ensuring compatibility and consistency across infrastructure deployments.
- **Bridging gaps in official modules** – Providing solutions when AVM does not meet project-specific needs.
- **Streamlined for Innofactor projects** – Enhancing reusability and efficiency in our customer implementations.
- **Maintained and supported by Innofactor** – Ensuring long-term viability and compliance with evolving cloud best practices.

IVS enables and accelerates the development of cloud-native solutions by codifying Microsoft and Innofactor best practices while maintaining flexibility for customization.

  </td>
    <td style="border: none; margin:0; padding: 0;">
      <img src="{{%siteparam base%}}/images/ivs_cycle.png" width=65% alt="IVS development cycle" style="margin:0 auto;padding: 0;">
    </td>
  </tr>
</table>

## Modules

<table style="border: none; border-collapse: collapse; margin: 0; padding: 0;">
  <tr>
    <td style="border: none; padding: 0; width:55%">
        <img src="{{%siteparam base%}}/images/ivs_modules.png" width=80% alt="IVS module classifications">
    </td>
    <td style="border: none; padding: 0;">

Innofactor Verified Solutions provides two primary types of modules:

- **Resource Modules** – Used for deploying individual Azure resources and their required configurations.
- **Pattern Modules** – Represent reusable architectural patterns that standardize common deployment scenarios.
- **Utility Modules** - Shared resources for standards, including typing, naming, etc.

IVS modules are composable, meaning they:

- Are **flexible, generalized, and multi-purpose**.
- Integrate **child and extension resources** seamlessly.
- Improve **code quality** while ensuring a **consistent user experience**.

By leveraging IVS, teams can ensure faster, more reliable infrastructure deployments that align with both Microsoft and Innofactor best practices.
    </td>
  </tr>
</table>

{{% notice style="important" %}}
**IVS is owned, developed, and supported by Innofactor.**

If you encounter issues or require additional features, please raise a request in our internal repository. For official Microsoft AVMs, continue to use Microsoft’s GitHub issues and support channels.

<!-- See [Module Support]({{%siteparam base%}}/help-support/module-support) for more details. -->
{{% /notice %}}

<!-- ## Next Steps

<table style="border: none; border-collapse: collapse; margin: 0; padding: 0;">
  <tr>
    <td style="border: none; padding: 0; width:60%">

1. Review the [Overview]({{% siteparam base %}}/overview/introduction)
2. Explore the [Module Classification Definitions]({{% siteparam base %}}/specs/shared/module-classifications/)
3. Review the [Specifications]({{% siteparam base %}}/specs/module-specs/)
4. Check the [FAQ]({{% siteparam base %}}/faq/)
5. Learn how to [contribute to IVS]({{% siteparam base %}}/contributing/)
    </td>
    <td style="border: none; padding: 0;">

    ![IVS]({{%siteparam base%}}/images/ivs_logo.png?width=10vw "IVS")

    </td>
  </tr>
</table>
 -->
